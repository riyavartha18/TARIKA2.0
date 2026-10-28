"""Supplier replenishment orders for Stock to Be Ordered.

A replenishment order records that the warehouse has asked a supplier for more
stock of a product. It is deliberately NOT a customer sales order, so it lives in
its own ``public.replenishment_orders`` table and never touches ``public.orders``.

Business rules enforced here (server side, parameterized SQL / ORM):

  * A single-product reorder (the "Order" button) adds its quantity straight to
    ``products.available_quantity`` immediately, in the SAME transaction that
    persists the purchase order, and flags that order ``stock_applied``.
  * A goods receipt on a ``stock_applied`` order records the delivered quantity
    but never re-adds those units, so the same stock is not counted twice. A
    plain (bulk) purchase order that did not pre-apply stock still gains its
    accepted quantity when its goods are physically received.
  * The same unfulfilled need cannot be ordered twice: while a Pending purchase
    order exists for a product, a new individual order for it is refused, so a
    double-click / retry can never increment the stock twice.
"""

import datetime

from django.db import connection, transaction

from catalog.cache import bump_catalog_version
from catalog.models import Product
from stock_to_be_ordered.models import ReplenishmentOrder
from stock_to_be_ordered.services.forecasting import (
    clean_demand_tier,
    fetch_demand_orderable,
    fetch_high_demand_orderable,
)


class ReplenishmentError(Exception):
    """Raised for a business-rule violation the caller should surface."""


def _now():
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')


def allocate_po_key():
    """Next sequential PO key ('PRO#######'). Advisory-locked for concurrency."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", ['replenishment_po_key'])
        cursor.execute(
            """
            SELECT coalesce(max(substring(po_key from 4)::bigint), 0) + 1
            FROM public.replenishment_orders
            WHERE po_key LIKE 'PRO%%' AND substring(po_key from 4) ~ '^[0-9]+$';
            """
        )
        next_number = cursor.fetchone()[0]
    return f"PRO{int(next_number):07d}"


def _create_po(product, quantity, created_by, demand_tier=None, stock_applied=False):
    po = ReplenishmentOrder.objects.create(
        po_key=allocate_po_key(),
        product_key=product.product_id,
        product_name=product.product_name,
        quantity_ordered=int(quantity),
        quantity_received=0,
        status=ReplenishmentOrder.STATUS_PENDING,
        demand_tier=demand_tier,
        stock_applied=stock_applied,
        created_by=created_by,
        created_at=_now(),
        updated_at=_now(),
    )
    return po


def _pending_po(product_key):
    return (
        ReplenishmentOrder.objects
        .filter(product_key=product_key, status=ReplenishmentOrder.STATUS_PENDING)
        .order_by('-created_at')
        .first()
    )


@transaction.atomic
def create_replenishment_order(product_key, quantity, created_by=None):
    """Place a single-product reorder and add `quantity` units to stock now.

    This is the reorder ("Order") button's business rule: the requested quantity
    is applied to ``products.available_quantity`` immediately, in the same
    transaction that persists the replenishment order, so both either save or
    roll back together. The purchase order is flagged ``stock_applied`` so the
    separate goods-receipt step never adds the same units a second time.

    Duplicate protection: while a Pending purchase order for the product still
    exists the request is refused, so a double-click / retry cannot increment
    the stock twice.
    """
    product_key = str(product_key or '').strip()
    if not product_key:
        raise ReplenishmentError("A product is required.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ReplenishmentError("Order quantity must be a whole number.")
    if quantity <= 0:
        raise ReplenishmentError("Order quantity must be greater than zero.")

    product = Product.objects.filter(product_id=product_key, is_active=True).first()
    if not product:
        raise ReplenishmentError("Product not found or is archived.")

    # Serialise concurrent reorders of the SAME product for the rest of this
    # transaction. A duplicate double-click / retry waits here, then sees the
    # pending PO the first request committed and is refused below, so the stock
    # can never be incremented twice by two simultaneous submissions.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s));",
            ['reorder_' + product_key],
        )

    existing = _pending_po(product_key)
    if existing:
        raise ReplenishmentError(
            f"An order for this product is already pending "
            f"({existing.po_key}: {existing.quantity_ordered} units). "
            "Receive it before ordering again."
        )

    po = _create_po(product, quantity, created_by, stock_applied=True)

    # Apply the ordered quantity to the canonical stock now. The row is locked
    # (select_for_update) and the new value is current + quantity read under the
    # lock, never a stale frontend number, so a concurrent edit cannot race it.
    locked = Product.objects.select_for_update().filter(product_id=product_key).first()
    if not locked:
        raise ReplenishmentError("The ordered product no longer exists.")
    new_stock = (locked.available_quantity or 0) + int(quantity)
    locked.available_quantity = new_stock
    locked.save(update_fields=['available_quantity'])

    bump_catalog_version()
    return po


@transaction.atomic
def order_all_high_demand(created_by=None):
    """Order the recommended quantity for every High-demand product not already
    on order. Returns a summary; per-item failures are collected, not swallowed."""
    result = fetch_high_demand_orderable()
    if not result.get('success'):
        raise ReplenishmentError(result.get('error', 'Demand model unavailable.'))

    items = result['items']
    created, skipped, failed = [], 0, []
    for item in items:
        product = Product.objects.filter(
            product_id=item['product_key'], is_active=True
        ).first()
        if not product:
            skipped += 1
            continue
        if _pending_po(item['product_key']):
            skipped += 1
            continue
        try:
            po = _create_po(product, item['recommended_qty'], created_by)
            created.append({
                'po_key': po.po_key,
                'product_key': product.product_id,
                'product_name': product.product_name,
                'quantity_ordered': po.quantity_ordered,
            })
        except Exception as exc:  # noqa: BLE001 - record per-item failure clearly
            failed.append({'product_key': item['product_key'], 'error': str(exc)})

    return {
        'requested': len(items),
        'created_count': len(created),
        'skipped_count': skipped,
        'failed_count': len(failed),
        'total_quantity': sum(c['quantity_ordered'] for c in created),
        'orders': created,
        'failures': failed,
    }


@transaction.atomic
def order_all_demand(tier, created_by=None, product_keys=None):
    """Place a supplier PO for the recommended quantity of a demand tier.

    ``product_keys`` optionally narrows the order to the products staff kept
    selected in the bulk review dialog. Only products that are genuinely
    orderable for the tier (still short and not already covered by a Pending
    PO) are turned into purchase orders: an unknown or no-longer-eligible key
    is reported as *skipped* and never force-orders stock. As with every create
    path a PO records intent only - ``products.available_quantity`` is not
    touched here.
    """
    tier = clean_demand_tier(tier)
    result = fetch_demand_orderable(tier)
    if not result.get('success'):
        raise ReplenishmentError(result.get('error', 'Demand model unavailable.'))

    orderable = {str(item['product_key']): item for item in result['items']}

    if product_keys is None:
        candidates = list(orderable.keys())
    else:
        candidates, seen = [], set()
        for key in product_keys:
            cleaned = str(key or '').strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            candidates.append(cleaned)

    created, skipped, failed = [], 0, []
    for key in candidates:
        item = orderable.get(key)
        if not item:
            # Unknown, no longer short, or already covered by a pending PO.
            skipped += 1
            continue
        product = Product.objects.filter(product_id=key, is_active=True).first()
        if not product or _pending_po(key):
            skipped += 1
            continue
        try:
            po = _create_po(product, item['recommended_qty'], created_by,
                            demand_tier=tier)
            created.append({
                'po_key': po.po_key,
                'product_key': product.product_id,
                'product_name': product.product_name,
                'quantity_ordered': po.quantity_ordered,
            })
        except Exception as exc:  # noqa: BLE001 - record per-item failure clearly
            failed.append({
                'product_key': key,
                'product_name': item.get('product_name'),
                'error': str(exc),
            })

    return {
        'requested': len(candidates),
        'tier': tier,
        'created_count': len(created),
        'skipped_count': skipped,
        'failed_count': len(failed),
        'total_quantity': sum(c['quantity_ordered'] for c in created),
        'orders': created,
        'failures': failed,
    }


@transaction.atomic
def receive_replenishment_order(po_key, received_qty=None, _bump_cache=True):
    """Record that some or all of the ordered goods were received.

    Partial receipts are supported:

      * A receipt smaller than the outstanding quantity leaves the purchase
        order ``Pending`` (so its remaining quantity keeps counting toward the
        pending-order / Stock-to-Be-Ordered calculations).
      * The order is only marked ``Received`` once the outstanding quantity
        reaches zero.
      * Zero, negative and over-receipt quantities are rejected outright (an
        over-receipt would silently change stock for a quantity nobody ordered),
        and ``available_quantity`` is increased only by the accepted quantity.

    The purchase-order row is locked (``select_for_update``) so two simultaneous
    receipts of the same order are serialised and can never double-count stock;
    the canonical product row is then locked before its stock is adjusted so a
    concurrent product edit cannot race the receipt.
    """
    po = (
        ReplenishmentOrder.objects
        .select_for_update()
        .filter(po_key=str(po_key or '').strip())
        .first()
    )
    if not po:
        raise ReplenishmentError("Replenishment order not found.")
    if po.status != ReplenishmentOrder.STATUS_PENDING:
        raise ReplenishmentError(
            f"Order {po.po_key} is already {po.status.lower()} and cannot be received again."
        )

    outstanding = max(0, po.quantity_ordered - po.quantity_received)
    if outstanding <= 0:
        raise ReplenishmentError(
            f"Order {po.po_key} has no outstanding quantity left to receive."
        )

    if received_qty is None:
        add_qty = outstanding
    else:
        try:
            add_qty = int(received_qty)
        except (TypeError, ValueError):
            raise ReplenishmentError("Received quantity must be a whole number.")
        if add_qty <= 0:
            raise ReplenishmentError("Received quantity must be greater than zero.")
        if add_qty > outstanding:
            raise ReplenishmentError(
                f"Received quantity {add_qty} exceeds the outstanding {outstanding} unit(s). "
                "Over-receipts are not supported."
            )

    # Lock the canonical product row, then apply the accepted received stock.
    # A reorder purchase order already added its units to available_quantity the
    # moment it was placed (stock_applied), so the physical receipt only records
    # the received quantity and must NOT increment stock a second time. A plain
    # (bulk) purchase order adds the accepted quantity here, as before.
    product = (
        Product.objects.select_for_update().filter(product_id=po.product_key).first()
    )
    if not product:
        raise ReplenishmentError("The ordered product no longer exists.")

    if po.stock_applied:
        new_stock = product.available_quantity or 0
    else:
        new_stock = (product.available_quantity or 0) + add_qty
        product.available_quantity = new_stock
        product.save(update_fields=['available_quantity'])

    po.quantity_received = po.quantity_received + add_qty
    remaining = po.quantity_ordered - po.quantity_received
    po.updated_at = _now()
    if remaining <= 0:
        po.status = ReplenishmentOrder.STATUS_RECEIVED
        po.received_at = _now()
        po.save(update_fields=['quantity_received', 'status', 'received_at', 'updated_at'])
    else:
        # Still outstanding -> remains Pending so pending/Stock-to-Be-Ordered
        # maths keeps counting the remaining quantity as not-yet-received.
        po.save(update_fields=['quantity_received', 'updated_at'])

    if _bump_cache:
        bump_catalog_version()

    return po, add_qty, new_stock


@transaction.atomic
def update_replenishment_order(po_key, quantity):
    """Edit the proposed reorder quantity of a Pending purchase order.

    Editing changes only what we asked the supplier for, never what we hold:
    ``products.available_quantity`` is untouched. It is allowed only while the
    order is Pending *and* nothing has been received yet, so the outstanding
    (ordered - received) maths stays consistent; a partially or fully received
    order must be received in full or cancelled instead.
    """
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ReplenishmentError("Order quantity must be a whole number.")
    if quantity <= 0:
        raise ReplenishmentError("Order quantity must be greater than zero.")

    po = (
        ReplenishmentOrder.objects
        .select_for_update()
        .filter(po_key=str(po_key or '').strip())
        .first()
    )
    if not po:
        raise ReplenishmentError("Replenishment order not found.")
    if po.status != ReplenishmentOrder.STATUS_PENDING:
        raise ReplenishmentError(
            f"Order {po.po_key} is {po.status.lower()} and can no longer be edited."
        )
    if (po.quantity_received or 0) > 0:
        raise ReplenishmentError(
            f"{po.quantity_received} unit(s) of {po.po_key} were already received; "
            "receive the remaining quantity or cancel instead of editing."
        )

    po.quantity_ordered = quantity
    po.updated_at = _now()
    po.save(update_fields=['quantity_ordered', 'updated_at'])
    return po


@transaction.atomic
def cancel_replenishment_order(po_key):
    """Withdraw a Pending purchase order before the goods arrive.

    Cancelling only removes the outstanding request to the supplier - it never
    changes ``products.available_quantity``. Units already received stay on hand
    (they physically arrived); cancelling simply stops the remaining quantity
    from counting toward the pending-order maths, so the product becomes
    orderable again. A completed or already-cancelled order cannot be cancelled.
    """
    po = (
        ReplenishmentOrder.objects
        .select_for_update()
        .filter(po_key=str(po_key or '').strip())
        .first()
    )
    if not po:
        raise ReplenishmentError("Replenishment order not found.")
    if po.status != ReplenishmentOrder.STATUS_PENDING:
        raise ReplenishmentError(
            f"Order {po.po_key} is already {po.status.lower()} and cannot be cancelled."
        )

    po.status = ReplenishmentOrder.STATUS_CANCELLED
    po.updated_at = _now()
    po.save(update_fields=['status', 'updated_at'])
    return po


def list_replenishment_orders(status=None, product_key=None, limit=50):
    qs = ReplenishmentOrder.objects.all()
    if status:
        qs = qs.filter(status=status)
    if product_key:
        qs = qs.filter(product_key=str(product_key).strip())
    return list(qs[:limit])
