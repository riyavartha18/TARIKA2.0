"""Create a throwaway customer with one real order, for browser verification.
Prints email + password + customer_id. Clean up with _cleanup_orders_demo.py.
"""
from accounts.services.supabase_auth import SupabaseAuthService
from accounts.models import Customer
from catalog.models import Product
from cart.services import CartService
from orders.services import OrderCreationService

EMAIL = 'catmove_demo@example.com'
PASSWORD = 'Demo#Pass123'

existing = Customer.objects.filter(email=EMAIL).first()
if existing:
    cid = existing.customer_id
else:
    res = SupabaseAuthService.register_customer(
        email=EMAIL, password=PASSWORD, full_name='Category Move Demo')
    cid = res['user']['customer_id']

from accounts.models import Customer as C
customer = C.objects.get(customer_id=cid)

prod = (Product.objects.filter(available_quantity__gte=3, discount_price__isnull=False).first())
CartService.clear_cart(customer)
CartService.add_to_cart(customer, prod.product_id, 1)
orders = OrderCreationService.create_orders_from_cart(customer, {'payment_method': 'COD'})
print('DEMO_EMAIL', EMAIL)
print('DEMO_PASSWORD', PASSWORD)
print('DEMO_CUSTOMER_ID', cid)
print('DEMO_ORDER_IDS', [o.order_id for o in orders])
