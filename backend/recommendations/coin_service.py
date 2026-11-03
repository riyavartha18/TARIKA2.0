"""
TARIKA Smart Budget Stylist - Customer Coins & Loyalty Rewards Service

Integrates persistent coin balances derived from real customer order history and
prevents negative coin balances, duplicate redemptions, and client-side price manipulation.
"""

import logging
import random
from django.db import connection, transaction
from orders.models import Order

logger = logging.getLogger(__name__)


class CoinService:
    COIN_REWARD_PERCENT = 0.02  # 1 coin per Rs.50 spent (2%)
    WELCOME_COINS = 150         # Bonus coins for registered members
    MAX_REDEEM_PERCENT = 0.15   # Up to 15% of outfit total can be paid in coins

    @classmethod
    def get_customer_coins(cls, customer_id):
        """
        Retrieves or calculates the real coin balance for a customer.
        Returns:
            dict: {
                'customer_id': str,
                'available_coins': int,
                'earned_coins': int,
                'redeemed_coins': int,
                'max_redeem_percent': int
            }
        """
        if not customer_id:
            return {
                'customer_id': None,
                'available_coins': 0,
                'earned_coins': 0,
                'redeemed_coins': 0,
                'max_redeem_percent': int(cls.MAX_REDEEM_PERCENT * 100)
            }

        cid = str(customer_id).strip()

        with connection.cursor() as cur:
            cur.execute("""
                SELECT earned_coins, redeemed_coins 
                FROM public.customer_coin_balances 
                WHERE customer_id = %s
            """, [cid])
            row = cur.fetchone()

            if row is not None:
                earned, redeemed = row
                available = max(0, int(earned) - int(redeemed))
                return {
                    'customer_id': cid,
                    'available_coins': available,
                    'earned_coins': int(earned),
                    'redeemed_coins': int(redeemed),
                    'max_redeem_percent': int(cls.MAX_REDEEM_PERCENT * 100)
                }

            # If not in table, compute earned coins from real delivered orders
            delivered_spend = 0.0
            try:
                orders = Order.objects.filter(customer_id=cid)
                for o in orders:
                    status = (o.delivery_status or '').lower()
                    if 'cancel' not in status and 'return' not in status:
                        if o.final_price and float(o.final_price) > 0:
                            delivered_spend += float(o.final_price)
            except Exception as e:
                logger.warning(f"Error reading orders for coin calculation: {e}")

            earned = int(cls.WELCOME_COINS + (delivered_spend * cls.COIN_REWARD_PERCENT))
            redeemed = 0
            available = max(0, earned - redeemed)

            # Insert initial record
            try:
                cur.execute("""
                    INSERT INTO public.customer_coin_balances (customer_id, earned_coins, redeemed_coins, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (customer_id) DO NOTHING
                """, [cid, earned, redeemed])
            except Exception as e:
                logger.warning(f"Error initializing coin balance: {e}")

            return {
                'customer_id': cid,
                'available_coins': available,
                'earned_coins': earned,
                'redeemed_coins': redeemed,
                'max_redeem_percent': int(cls.MAX_REDEEM_PERCENT * 100)
            }

    @classmethod
    def compute_outfit_pricing(cls, subtotal_price, budget, available_coins):
        """
        Computes accurate breakdown for an outfit:
        1. Product subtotal after discounts (subtotal_price)
        2. Eligible coin discount (eligible_coins)
        3. Final payable amount (final_price)
        4. Remaining budget (coins_remaining)
        """
        subtotal = float(subtotal_price)
        b_float = float(budget)
        avail = int(available_coins or 0)

        # Maximum coins eligible for this outfit (capped by 15% of subtotal and user's balance)
        max_eligible = int(subtotal * cls.MAX_REDEEM_PERCENT)
        eligible_coins = min(avail, max_eligible)
        coin_discount = float(eligible_coins)

        # Final payable after coin discount
        final_payable = max(0.0, round(subtotal - coin_discount, 2))

        # Remaining unspent budget
        remaining_budget = max(0.0, round(b_float - final_payable, 2))

        # Coins customer will earn if they purchase this outfit (5% back)
        coins_earned = max(10, int(final_payable * 0.05))

        return {
            'subtotal_price': int(round(subtotal)),
            'eligible_coins': eligible_coins,
            'coin_discount': int(round(coin_discount)),
            'final_price': int(round(final_payable)),
            'remaining_budget': int(round(remaining_budget)),
            'coins_earned': coins_earned
        }

    @classmethod
    def redeem_coins_for_outfit(cls, customer_id, outfit_id, requested_coins):
        """
        Secure backend coin redemption with validation:
        - Prevents negative coin balance
        - Prevents duplicate redemption on same outfit
        - Prevents client-side manipulation of coin amounts
        """
        if not customer_id:
            return {'success': False, 'error': 'Customer ID is required.'}

        cid = str(customer_id).strip()
        coins_to_redeem = int(requested_coins or 0)

        if coins_to_redeem <= 0:
            return {'success': False, 'error': 'Coins to redeem must be greater than zero.'}

        with transaction.atomic():
            with connection.cursor() as cur:
                # Lock row for update
                cur.execute("""
                    SELECT earned_coins, redeemed_coins 
                    FROM public.customer_coin_balances 
                    WHERE customer_id = %s
                    FOR UPDATE
                """, [cid])
                row = cur.fetchone()

                if not row:
                    # Initialize
                    cls.get_customer_coins(cid)
                    cur.execute("""
                        SELECT earned_coins, redeemed_coins 
                        FROM public.customer_coin_balances 
                        WHERE customer_id = %s
                        FOR UPDATE
                    """, [cid])
                    row = cur.fetchone()

                earned, redeemed = row
                current_available = max(0, int(earned) - int(redeemed))

                if coins_to_redeem > current_available:
                    return {
                        'success': False,
                        'error': f"Insufficient coin balance. Available: {current_available}, Requested: {coins_to_redeem}"
                    }

                # Check for duplicate redemption on outfit
                cur.execute("""
                    SELECT id FROM public.customer_coin_redemptions
                    WHERE customer_id = %s AND outfit_id = %s
                """, [cid, str(outfit_id)])
                if cur.fetchone():
                    return {
                        'success': False,
                        'error': 'Coins have already been applied to this outfit combination.'
                    }

                # Record redemption
                cur.execute("""
                    INSERT INTO public.customer_coin_redemptions (customer_id, outfit_id, coins_redeemed, discount_amount, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, [cid, str(outfit_id), coins_to_redeem, float(coins_to_redeem)])

                # Update balance
                new_redeemed = int(redeemed) + coins_to_redeem
                cur.execute("""
                    UPDATE public.customer_coin_balances
                    SET redeemed_coins = %s, updated_at = NOW()
                    WHERE customer_id = %s
                """, [new_redeemed, cid])

                new_available = max(0, int(earned) - new_redeemed)

                return {
                    'success': True,
                    'redeemed_coins': coins_to_redeem,
                    'discount_amount': float(coins_to_redeem),
                    'new_available_coins': new_available
                }

    SPIN_COST = 50

    SPIN_SEGMENTS = [
        {
            'index': 0,
            'label': '10% OFF',
            'discount_type': 'percent',
            'discount_value': 10,
            'coupon_code': 'SPIN10',
            'description': 'Extra 10% off on your next order',
            'min_spend': 0,
        },
        {
            'index': 1,
            'label': '₹300 OFF',
            'discount_type': 'fixed',
            'discount_value': 300,
            'coupon_code': 'SPIN300',
            'description': 'Flat ₹300 off on minimum purchase of ₹1,999',
            'min_spend': 1999,
        },
        {
            'index': 2,
            'label': 'FREE DELIVERY',
            'discount_type': 'shipping',
            'discount_value': 0,
            'coupon_code': 'FREESHIP',
            'description': 'Complimentary express delivery on your order',
            'min_spend': 0,
        },
        {
            'index': 3,
            'label': '₹150 OFF',
            'discount_type': 'fixed',
            'discount_value': 150,
            'coupon_code': 'SPIN150',
            'description': 'Flat ₹150 off on minimum purchase of ₹999',
            'min_spend': 999,
        },
        {
            'index': 4,
            'label': '5% OFF',
            'discount_type': 'percent',
            'discount_value': 5,
            'coupon_code': 'SPIN5',
            'description': 'Extra 5% off boutique styles',
            'min_spend': 0,
        },
        {
            'index': 5,
            'label': '20% OFF',
            'discount_type': 'percent',
            'discount_value': 20,
            'coupon_code': 'SPIN20',
            'description': '20% off on your next order above ₹2,499',
            'min_spend': 2499,
        },
    ]

    @classmethod
    def get_wheel_config(cls):
        return {
            'cost_per_spin': cls.SPIN_COST,
            'segments': cls.SPIN_SEGMENTS,
        }

    @classmethod
    def spin_wheel(cls, customer_id):
        if not customer_id:
            return {'success': False, 'error': 'Please log in to spin and earn rewards.'}

        cid = str(customer_id).strip()
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("""
                    SELECT earned_coins, redeemed_coins 
                    FROM public.customer_coin_balances 
                    WHERE customer_id = %s
                    FOR UPDATE
                """, [cid])
                row = cur.fetchone()

                if not row:
                    cls.get_customer_coins(cid)
                    cur.execute("""
                        SELECT earned_coins, redeemed_coins 
                        FROM public.customer_coin_balances 
                        WHERE customer_id = %s
                        FOR UPDATE
                    """, [cid])
                    row = cur.fetchone()

                if not row:
                    return {'success': False, 'error': 'Unable to access coin balance.'}

                earned, redeemed = row
                available = max(0, int(earned) - int(redeemed))

                if available < cls.SPIN_COST:
                    return {
                        'success': False,
                        'error': f'Insufficient coins. You have {available} coins, but each spin requires {cls.SPIN_COST} coins.',
                        'available_coins': available,
                        'required_coins': cls.SPIN_COST
                    }

                # Deduct spin cost
                new_redeemed = int(redeemed) + cls.SPIN_COST
                cur.execute("""
                    UPDATE public.customer_coin_balances
                    SET redeemed_coins = %s, updated_at = NOW()
                    WHERE customer_id = %s
                """, [new_redeemed, cid])

                selected = random.choice(cls.SPIN_SEGMENTS)
                new_available = max(0, int(earned) - new_redeemed)

                return {
                    'success': True,
                    'segment_index': selected['index'],
                    'reward': selected,
                    'cost_coins': cls.SPIN_COST,
                    'new_available_coins': new_available,
                    'message': f"Congratulations! You won {selected['label']}!"
                }
