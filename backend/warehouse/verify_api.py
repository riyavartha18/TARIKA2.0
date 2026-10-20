import os
import sys
import django

# Set up Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from catalog.models import Product
from warehouse.services import WarehouseService
from warehouse.serializers import (
    WarehouseProductDetailSerializer,
    WarehouseProductUpdateSerializer,
)

def run_verification():
    print("=== STARTING PRODUCT DETAIL & EDIT API VERIFICATION ===")
    
    # 1. Fetch first available product
    first_product = Product.objects.first()
    if not first_product:
        print("ERROR: No products found in database!")
        return False
        
    product_id = first_product.product_id
    print(f"[1] Testing get_product_detail for product_id: {product_id}")
    
    # 2. Get product detail via WarehouseService
    prod = WarehouseService.get_product_detail(product_id)
    print(f"    - Found product: {prod.product_name}")
    print(f"    - Category: {prod.category.category_name if prod.category else 'N/A'}")
    
    # 3. Test Detail Serializer
    detail_serializer = WarehouseProductDetailSerializer(prod)
    data = detail_serializer.data
    print("    - Serializer output:")
    print(f"        total_stock: {data.get('total_stock')}")
    print(f"        in_stock: {data.get('in_stock')}")
    print(f"        availability_label: {data.get('availability_label')}")
    assert 'total_stock' in data, "total_stock missing from serializer"
    assert 'availability_label' in data, "availability_label missing from serializer"
    assert data.get('availability_label') in ('Available', 'Out of Stock'), "invalid availability_label"
    
    # 4. Test Update Serializer Validation
    print("\n[2] Testing WarehouseProductUpdateSerializer validation")
    invalid_data = {'product_name': '   '}
    val_serializer = WarehouseProductUpdateSerializer(data=invalid_data)
    assert not val_serializer.is_valid(), "Empty product_name should fail validation"
    print("    - Empty product_name correctly rejected with errors:", val_serializer.errors)
    
    valid_payload = {
        'product_name': prod.product_name,
        'description': prod.description or '',
        'base_price': prod.base_price,
        'selling_price': prod.selling_price,
        'gender': prod.gender or '',
        'color': prod.color or '',
        'size': prod.size or '',
        'material': prod.material or '',
        'is_active': prod.is_active if prod.is_active is not None else True
    }
    val_serializer_ok = WarehouseProductUpdateSerializer(data=valid_payload)
    assert val_serializer_ok.is_valid(), f"Valid payload failed: {val_serializer_ok.errors}"
    print("    - Valid payload passed validation successfully.")
    
    # 5. Test WarehouseService.update_product & stock quantity update
    print(f"\n[3] Testing update_product & stock quantity update on DB for product_id: {product_id}")
    original_name = prod.product_name
    test_name = original_name + " (Verified)"
    original_stock = detail_serializer.data.get('total_stock', 0)
    test_stock = original_stock + 25
    
    # Update product name & stock_quantity
    updated_prod = WarehouseService.update_product(product_id, {'product_name': test_name, 'stock_quantity': test_stock})
    assert updated_prod.product_name == test_name, "Product name was not updated in DB"
    updated_detail = WarehouseProductDetailSerializer(updated_prod).data
    assert updated_detail.get('total_stock') == test_stock, f"Expected stock {test_stock}, got {updated_detail.get('total_stock')}"
    print(f"    - Updated name in DB to: '{updated_prod.product_name}'")
    print(f"    - Updated stock quantity in DB to: {updated_detail.get('total_stock')}")
    
    # Revert back to original name & stock
    reverted_prod = WarehouseService.update_product(product_id, {'product_name': original_name, 'stock_quantity': original_stock})
    assert reverted_prod.product_name == original_name, "Failed to revert product name"
    print(f"    - Reverted name & stock in DB cleanly to: '{reverted_prod.product_name}', stock={original_stock}")
    
    print("\n=== ALL VERIFICATIONS PASSED SUCCESSFULLY ===")
    return True

if __name__ == '__main__':
    run_verification()
