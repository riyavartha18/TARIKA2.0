# TARIKA — Part 2B: Customer Wishlist & Bag/Cart Module

## Overview
The `cart` app implements the complete Customer **Wishlist** and **Shopping Bag (Cart)** backend APIs for the TARIKA fashion retail platform. It connects to the Supabase PostgreSQL database using unmanaged Django models (`managed = False`), enforces customer isolation via authenticated `Customer` profiles, checks real-time inventory levels before modifying bag contents, and calculates accurate subtotal and total sums.

---

## Mapped Database Tables

| Table | Primary Key | Key Columns | Description |
| :--- | :--- | :--- | :--- |
| `wishlist_items` | `id` (BIGSERIAL) | `customer_id`, `product_id`, `created_at` | Stores customer wishlist items with a `UNIQUE(customer_id, product_id)` constraint to prevent duplicates. |
| `cart_items` | `id` (BIGSERIAL) | `customer_id`, `product_id`, `quantity`, `created_at`, `updated_at` | Stores customer bag items with a `UNIQUE(customer_id, product_id)` constraint and `quantity > 0` validation. |
| `customer` | `customer_id` (text) | `auth_user_id`, `email`, `full_name`, `is_active` | Scopes all customer data queries for strict multi-tenant customer isolation. |
| `products` | `product_id` (text) | `product_name`, `selling_price`, `base_price`, `sku`, `is_active` | Catalog product information and pricing. |
| `inventory` | `inventory_id` (text) | `product_id`, `warehouse_id`, `stock_quantity` | Real-time stock across fulfillment centers used for pre-add and pre-update quantity validation. |

---

## Security & Customer Isolation

1. **Authentication**: All endpoints require a valid Supabase JWT Bearer token in the `Authorization: Bearer <token>` header.
2. **Permission**: Protected by `accounts.permissions.IsCustomer`. Unauthenticated requests receive HTTP 401; non-customer roles (Admin, Warehouse Manager, Delivery Partner) receive HTTP 403 Forbidden.
3. **Data Isolation**: The customer identity is dynamically resolved via `request.user.profile.customer_id`. Every query explicitly filters `customer_id=customer_id`. A customer can never view, update, or remove items belonging to another customer.

---

## API Endpoints

### 1. Wishlist APIs

#### A. View Wishlist
- **URL**: `GET /api/wishlist/`
- **Response**:
```json
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "product_id": "d1cc733a-455f-47eb-a76b-e0e86fbe7442",
      "product": {
        "product_id": "d1cc733a-455f-47eb-a76b-e0e86fbe7442",
        "product_name": "Puff Sleeve Dress",
        "category_name": "Dresses",
        "sku": "D-0015-590",
        "color": "Mustard",
        "size": "M",
        "material": "Rayon",
        "base_price": 1670,
        "selling_price": 1670,
        "in_stock": true,
        "total_stock": 24,
        "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80"
      },
      "created_at": "2026-09-06T08:10:11.307420Z"
    }
  ]
}
```

#### B. Add to Wishlist
- **URL**: `POST /api/wishlist/`
- **Payload**: `{"product_id": "d1cc733a-455f-47eb-a76b-e0e86fbe7442"}`
- **Duplicate Prevention**: If the item already exists in the customer's wishlist, returns HTTP 200 with `already_in_wishlist: true` and the existing item data without raising errors or creating duplicates. Newly added items return HTTP 201 Created.

#### C. Remove from Wishlist
- **URL**: `DELETE /api/wishlist/<product_id>/`
- **Response**: HTTP 200 OK with `{"message": "Product removed from wishlist successfully."}`.

---

### 2. Bag / Cart APIs

*Note: All endpoints are accessible interchangeably at `/api/cart/` and `/api/bag/`.*

#### A. View Bag
- **URL**: `GET /api/cart/` or `GET /api/bag/`
- **Response**:
```json
{
  "items": [
    {
      "id": 1,
      "product_id": "d1cc733a-455f-47eb-a76b-e0e86fbe7442",
      "product": {
        "product_id": "d1cc733a-455f-47eb-a76b-e0e86fbe7442",
        "product_name": "Puff Sleeve Dress",
        "category_name": "Dresses",
        "sku": "D-0015-590",
        "color": "Mustard",
        "size": "M",
        "material": "Rayon",
        "base_price": 1670,
        "selling_price": 1670,
        "in_stock": true,
        "available_stock": 24,
        "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80"
      },
      "quantity": 2,
      "unit_price": 1670,
      "line_total": 3340,
      "is_stock_available": true,
      "created_at": "2026-09-06T08:10:11.307420Z",
      "updated_at": "2026-09-06T08:10:11.307420Z"
    }
  ],
  "total_items": 2,
  "subtotal": 3340,
  "total": 3340
}
```

#### B. Add Product to Bag
- **URL**: `POST /api/cart/` or `POST /api/bag/`
- **Payload**: `{"product_id": "<uuid>", "quantity": 1}`
- **Stock Validation**: Queries real-time stock across warehouses in `inventory`. Rejects with HTTP 400 if product is out of stock or if `(existing_quantity + requested_quantity) > available_stock`.

#### C. Update Quantity
- **URL**: `PATCH /api/cart/<product_id>/` (or `PUT`)
- **Payload**: `{"quantity": 3}`
- **Stock Validation**: Checks that requested quantity does not exceed total available warehouse stock.

#### D. Remove Item from Bag
- **URL**: `DELETE /api/cart/<product_id>/`

#### E. Clear Entire Bag
- **URL**: `DELETE /api/cart/clear/`
