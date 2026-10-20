import datetime
from django.db.models import Q
from warehouse.models import Delivery, Order, Return


class DeliveryPartnerService:
    """
    Business service layer for Delivery Partner portal.
    Enforces strict employee data isolation so partners only see/modify
    deliveries assigned to their employee profile.
    """

    @staticmethod
    def get_assigned_deliveries(employee_id, status=None, search=None):
        """
        Returns deliveries assigned to the given delivery partner employee.
        Supports status filtering and search across delivery ID, order ID,
        customer name, city, phone, and address.
        """
        qs = (
            Delivery.objects
            .filter(assigned_employee_id=employee_id)
            .exclude(delivery_type__iexact='RETURN')
            .select_related('order__customer', 'assigned_employee', 'warehouse')
        )

        if status and status.strip().lower() not in ['all', '']:
            qs = qs.filter(delivery_status__iexact=status.strip())

        if search and search.strip():
            term = search.strip()
            qs = qs.filter(
                Q(delivery_id__icontains=term) |
                Q(order_id__icontains=term) |
                Q(order__customer__full_name__icontains=term) |
                Q(order__customer__city__icontains=term) |
                Q(order__customer__phone__icontains=term) |
                Q(order__shipping_address__icontains=term)
            )

        return qs.order_by('-dispatch_date', '-delivery_id')

    @staticmethod
    def get_delivery_detail(delivery_id, employee_id):
        """
        Fetch single delivery detail, strictly validating ownership.
        Raises Delivery.DoesNotExist if not found or not assigned to employee.
        """
        return (
            Delivery.objects
            .select_related('order__customer', 'assigned_employee', 'warehouse')
            .get(delivery_id=delivery_id, assigned_employee_id=employee_id)
        )

    @staticmethod
    def update_delivery_status(delivery_id, employee_id, new_status, reason=''):
        """
        Updates the status of an assigned delivery.
        Transitions: Assigned -> Picked Up -> In Transit -> Delivered (or Delayed / Failed).
        """
        delivery = (
            Delivery.objects
            .select_related('order', 'order__customer', 'assigned_employee', 'warehouse')
            .get(delivery_id=delivery_id, assigned_employee_id=employee_id)
        )

        # Normalize status to canonical capitalization
        valid_map = {
            'assigned': 'Assigned',
            'picked up': 'Picked Up',
            'in transit': 'In Transit',
            'delivered': 'Delivered',
            'delayed': 'Delayed',
            'failed': 'Failed',
        }
        canonical_status = valid_map.get(new_status.strip().lower(), new_status.strip())

        current_lower = (delivery.delivery_status or 'Assigned').strip().lower()
        target_lower = canonical_status.lower()

        # Strict lifecycle transitions:
        # Assigned -> Picked Up, Delayed, Failed
        # Picked Up -> In Transit, Delayed, Failed
        # In Transit -> Delivered, Delayed, Failed
        # Delayed -> In Transit, Picked Up, Failed
        # Failed -> In Transit (re-attempt)
        # Delivered -> terminal
        ALLOWED_TRANSITIONS = {
            'assigned': ['picked up', 'delayed', 'failed'],
            'picked up': ['in transit', 'delayed', 'failed'],
            'in transit': ['delivered', 'delayed', 'failed'],
            'delayed': ['in transit', 'picked up', 'failed'],
            'failed': ['in transit'],
            'delivered': [],
        }

        allowed_targets = ALLOWED_TRANSITIONS.get(current_lower, [])
        if target_lower != current_lower and target_lower not in allowed_targets:
            allowed_names = [valid_map[s] for s in allowed_targets if s in valid_map]
            allowed_desc = f": {', '.join(allowed_names)}" if allowed_names else " (terminal state)"
            raise ValueError(
                f"Invalid status transition from '{delivery.delivery_status}' to '{canonical_status}'. "
                f"Allowed transitions{allowed_desc}."
            )

        delivery.delivery_status = canonical_status
        now_date_str = datetime.date.today().strftime('%Y-%m-%d')
        now_iso = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if canonical_status == 'Delivered':
            delivery.actual_delivery_date = now_date_str
            delivery.failure_reason = None
            if delivery.order:
                delivery.order.order_status = 'delivered'
                delivery.order.updated_at = now_iso
                delivery.order.save(update_fields=['order_status', 'updated_at'])

        elif canonical_status in ['Delayed', 'Failed']:
            delivery.failure_reason = reason or delivery.failure_reason or f"Marked {canonical_status} by delivery partner"

        elif canonical_status in ['Picked Up', 'In Transit']:
            # Clear exception reason if transitioning back to normal flow unless reason explicitly passed
            if not reason:
                delivery.failure_reason = None
            if delivery.order and (delivery.order.order_status or '').lower() in ['pending', 'confirmed']:
                delivery.order.order_status = 'shipped'
                delivery.order.updated_at = now_iso
                delivery.order.save(update_fields=['order_status', 'updated_at'])

        delivery.save()
        return delivery

    @staticmethod
    def get_dashboard_metrics(employee_id):
        """
        Calculates real-time delivery performance metrics for the logged-in partner.
        """
        qs = Delivery.objects.filter(assigned_employee_id=employee_id)

        all_deliveries = list(qs.values('delivery_status'))
        total = len(all_deliveries)

        status_counts = {}
        for d in all_deliveries:
            st = (d.get('delivery_status') or '').strip().title()
            status_counts[st] = status_counts.get(st, 0) + 1

        pending_pickup = status_counts.get('Assigned', 0)
        picked_up = status_counts.get('Picked Up', 0)
        in_transit = status_counts.get('In Transit', 0)
        delivered = status_counts.get('Delivered', 0)
        delayed = status_counts.get('Delayed', 0)
        failed = status_counts.get('Failed', 0)

        active = pending_pickup + picked_up + in_transit
        exceptions = delayed + failed

        return {
            'total_assigned': total,
            'active_deliveries': active,
            'pending_pickup': pending_pickup,
            'picked_up': picked_up,
            'in_transit': in_transit,
            'delivered': delivered,
            'delayed': delayed,
            'failed': failed,
            'exceptions': exceptions,
        }

    @staticmethod
    def get_assigned_return_pickups(employee_id, status=None, search=None):
        """
        Returns return pickups assigned to the given delivery partner employee.
        Enforces strict employee data isolation.
        """
        qs = (
            Return.objects
            .filter(assigned_employee_id=employee_id)
            .select_related('order_item__product', 'customer', 'assigned_employee')
        )

        if status and status.strip().lower() not in ['all', '']:
            qs = qs.filter(return_status__iexact=status.strip())

        if search and search.strip():
            term = search.strip()
            qs = qs.filter(
                Q(return_id__icontains=term) |
                Q(order_item__order_id__icontains=term) |
                Q(customer__full_name__icontains=term) |
                Q(customer__city__icontains=term) |
                Q(customer__phone__icontains=term) |
                Q(order_item__product__product_name__icontains=term) |
                Q(return_reason__icontains=term)
            )

        return qs.order_by('-return_date', '-return_id')

    @staticmethod
    def get_return_pickup_detail(return_id, employee_id):
        """
        Fetch single return pickup, strictly validating assigned employee ownership.
        """
        return (
            Return.objects
            .select_related('order_item__product', 'customer', 'assigned_employee')
            .get(return_id=return_id, assigned_employee_id=employee_id)
        )

    @staticmethod
    def update_return_pickup_status(return_id, employee_id, new_status, reason=''):
        """
        Updates the status of an assigned return pickup.
        Controlled transitions:
          Pickup Assigned -> Pickup Accepted, Failed
          Pickup Accepted -> Picked Up, Failed
          Picked Up -> Received at Warehouse, Failed
          Failed -> Pickup Accepted (re-attempt)
        """
        ret = (
            Return.objects
            .select_related('order_item__product', 'customer', 'assigned_employee')
            .get(return_id=return_id, assigned_employee_id=employee_id)
        )

        canonical_map = {
            'pickup assigned': 'Pickup Assigned',
            'pickup accepted': 'Pickup Accepted',
            'picked up': 'Picked Up',
            'received at warehouse': 'Received at Warehouse',
            'completed': 'Completed',
            'failed': 'Failed',
        }
        canonical = canonical_map.get(new_status.strip().lower(), new_status.strip())
        current_lower = (ret.return_status or '').strip().lower()
        target_lower = canonical.lower()

        ALLOWED_TRANSITIONS = {
            'pickup assigned': ['pickup accepted', 'failed'],
            'pickup accepted': ['picked up', 'failed'],
            'picked up': ['received at warehouse', 'failed'],
            'received at warehouse': [],
            'completed': [],
            'failed': ['pickup accepted'],
        }

        allowed_targets = ALLOWED_TRANSITIONS.get(current_lower, [])
        if target_lower != current_lower and target_lower not in allowed_targets:
            allowed_names = [canonical_map[s] for s in allowed_targets if s in canonical_map]
            allowed_desc = f": {', '.join(allowed_names)}" if allowed_names else " (terminal state)"
            raise ValueError(
                f"Invalid return status transition from '{ret.return_status}' to '{canonical}'. "
                f"Allowed transitions{allowed_desc}."
            )

        ret.return_status = canonical
        if canonical == 'Failed' and reason:
            ret.condition_on_return = reason

        ret.save()

        # Keep linked delivery record synchronized if present
        del_rec = Delivery.objects.filter(return_record=ret).first()
        if del_rec:
            if canonical == 'Pickup Accepted':
                del_rec.delivery_status = 'Assigned'
            elif canonical == 'Picked Up':
                del_rec.delivery_status = 'In Transit'
            elif canonical == 'Received at Warehouse':
                del_rec.delivery_status = 'Delivered'
                del_rec.actual_delivery_date = datetime.date.today().isoformat()
            elif canonical == 'Failed':
                del_rec.delivery_status = 'Failed'
                del_rec.failure_reason = reason or "Pickup attempt failed"
            del_rec.save()

        return ret
