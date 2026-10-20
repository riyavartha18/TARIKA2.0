# TARIKA — Part 2A: Customer Product Catalog Module

## Overview
The `catalog` app implements the complete, publicly accessible Customer Product Catalog Backend for the **TARIKA** fashion retail platform. It connects directly to the existing Supabase PostgreSQL database using Django models with `managed = False` to preserve all existing records and schema integrity.

---

## Mapped Database Tables

All tables were inspected directly in the live Supabase PostgreSQL database:

| Table | Primary Key | Key Columns Mapped | Description |
| :--- | :--- | :--- | :--- |
| `categories` | `category_id` (text) | `category_name`, `parent_category_id`, `description`, `created_at` | 14 product categories. |
| `products` | `product_id` (text) | `product_name`, `category_id`, `manufacturer_id`, `sku`, `description`, `gender`, `color`, `size`, `material`, `cost_price`, `base_price`, `selling_price`, `launch_date`, `is_active`, `created_at`, `updated_at` | 420 fashion products. |
| `inventory` | `inventory_id` (text) | `product_id`, `warehouse_id`, `stock_quantity`, `reorder_level`, `last_restock_date` | 909 stock records across warehouses. |
| `warehouses` | `warehouse_id` (text) | `warehouse_name`, `city`, `state`, `country`, `capacity`, `manager_name`, `contact_number`, `created_at` | 4 regional fulfillment centers. |
| `order_items` | `order_item_id` (text)| `order_id`, `product_id`, `quantity`, `unit_price`, `discount`, `subtotal` | 14,157 customer order records. |
| `reviews` | `review_id` (text) | `product_id`, `customer_id`, `rating`, `review_text`, `sentiment_label`, `review_date` | 3,300 product customer reviews. |

---

## API Endpoints

All catalog endpoints are **publicly readable** (`AllowAny` permission). No JWT or login credentials are required.

### 1. Categories
- **Endpoint**: `GET /api/catalog/categories/`
- **Description**: Returns all product categories with their active product counts and curated boutique editorial images.
- **Sample Response**:
```json
[
  {
    "category_id": "47f429fb-bc65-48d1-8dd0-f85bac9ad00b",
    "category_name": "Dresses",
    "parent_category_id": null,
    "description": "Women's casual and party dresses",
    "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80",
    "product_count": 40,
    "created_at": "2023-08-14"
  }
]
```

---

### 2. Products List
- **Endpoint**: `GET /api/catalog/products/`
- **Description**: Returns paginated active products with filtering and sorting capabilities.
- **Query Parameters**:
  - `category` *(optional)*: Filter by `category_id` (UUID) or category name (e.g. `Dresses`, case-insensitive).
  - `search` *(optional)*: Case-insensitive search across `product_name`, `description`, `color`, `material`, and `sku`.
  - `min_price` *(optional)*: Minimum `selling_price` (inclusive).
  - `max_price` *(optional)*: Maximum `selling_price` (inclusive).
  - `sort` *(optional)*:
    - `newest`: Sort by newest launch date and creation timestamp (default).
    - `price_low_high`: Sort by price ascending.
    - `price_high_low`: Sort by price descending.
    - `name`: Sort alphabetically by product name.
  - `page` *(optional, default 1)*: Page number.
  - `page_size` *(optional, default 12, max 100)*: Items per page.
- **Sample Response**:
```json
{
  "count": 400,
  "total_pages": 34,
  "current_page": 1,
  "page_size": 12,
  "next": "http://127.0.0.1:8000/api/catalog/products/?page=2",
  "previous": null,
  "results": [
    {
      "product_id": "d1cc733a-455f-47eb-a76b-e0e86fbe7442",
      "product_name": "Puff Sleeve Dress",
      "category_id": "47f429fb-bc65-48d1-8dd0-f85bac9ad00b",
      "category_name": "Dresses",
      "sku": "D-0015-590",
      "description": "Puff Sleeve Dress in mustard, rayon blend, wrap dress style.",
      "gender": "women",
      "color": "Mustard",
      "size": "M",
      "material": "Rayon",
      "base_price": 1670,
      "selling_price": 1670,
      "launch_date": "2026-06-30",
      "is_active": true,
      "in_stock": true,
      "total_stock": 24,
      "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80"
    }
  ]
}
```

---

### 3. Product Detail
- **Endpoint**: `GET /api/catalog/products/<product_id>/`
- **Description**: Returns complete product information including every schema field, warehouse stock breakdown, and customer review summaries.
- **Sample Response**:
```json
{
  "product_id": "d1cc733a-455f-47eb-a76b-e0e86fbe7442",
  "product_name": "Puff Sleeve Dress",
  "category_id": "47f429fb-bc65-48d1-8dd0-f85bac9ad00b",
  "category_name": "Dresses",
  "category": {
    "category_id": "47f429fb-bc65-48d1-8dd0-f85bac9ad00b",
    "category_name": "Dresses",
    "parent_category_id": null,
    "description": "Women's casual and party dresses",
    "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80",
    "product_count": 40,
    "created_at": "2023-08-14"
  },
  "manufacturer_id": "481306d4-9af2-410d-a181-e55d57f23674",
  "sku": "D-0015-590",
  "description": "Puff Sleeve Dress in mustard, rayon blend, wrap dress style.",
  "gender": "women",
  "color": "Mustard",
  "size": "M",
  "material": "Rayon",
  "cost_price": 910,
  "base_price": 1670,
  "selling_price": 1670,
  "launch_date": "2026-06-30",
  "is_active": true,
  "created_at": "2026-06-30",
  "updated_at": "2026-07-23",
  "in_stock": true,
  "total_stock": 24,
  "inventory_breakdown": [
    {
      "warehouse_id": "8527dc10-e4f3-45a1-a5d7-166a6f03155c",
      "warehouse_name": "North Zone Fulfillment Center",
      "city": "Gurugram",
      "state": "Haryana",
      "stock_quantity": 24,
      "reorder_level": 17,
      "last_restock_date": "2026-08-10"
    }
  ],
  "rating_summary": {
    "average_rating": 4.25,
    "review_count": 4
  },
  "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80"
}
```

---

### 4. Featured Sections

#### A. New Arrivals
- **Endpoint**: `GET /api/catalog/new-arrivals/?limit=12`
- **Logic**: Returns products ordered by `-launch_date`, `-created_at`. Accepts optional `limit` parameter (default 12).

#### B. Trending
- **Endpoint**: `GET /api/catalog/trending/?limit=12`
- **Logic**: Computes aggregate sales volume from the `order_items` table (`Sum('order_items__quantity')`) using a correlated subquery, ordering products with highest customer purchase volume first.

#### C. Sale
- **Endpoint**: `GET /api/catalog/sale/?limit=12`
- **Logic**:
  1. *Primary*: Products where `base_price > selling_price`.
  2. *Fallback*: If all current database products have `base_price == selling_price`, derives products with documented promotional discount history in `order_items` (`discount > 0`), or lowest clearance pricing.

---

## Stock Calculation Logic

1. **`total_stock`**:
   Computed as the sum of `stock_quantity` across all warehouses in the `inventory` table for that `product_id`.
   ```sql
   COALESCE((SELECT SUM(stock_quantity) FROM inventory WHERE product_id = products.product_id), 0)
   ```
2. **`in_stock`**:
   Boolean flag evaluated as:
   ```python
   in_stock = total_stock > 0
   ```
3. **`inventory_breakdown`**:
   Exposes the per-warehouse stock distribution (warehouse name, location, and remaining units) without modifying any inventory record.

---

## Assumptions & Database Observations

1. **Unmanaged Models**: All models use `managed = False` and map directly to existing table names (`categories`, `products`, `inventory`, `warehouses`, `order_items`, `reviews`). Existing data is strictly preserved.
2. **Image Fields**: The database tables `categories` and `products` do not contain a native `image` or `image_url` column. The backend maps category names to high-resolution editorial imagery matching the TARIKA boutique design aesthetic as specified in Part 1 frontend.
3. **Date Formats**: Date fields (`launch_date`, `created_at`, `updated_at`, `review_date`) are stored as ISO-like strings (`YYYY-MM-DD`) in the Supabase schema and are exposed verbatim without loss of precision.
