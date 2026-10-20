# Recommendations App (TARIKA)

## Overview
The `recommendations` app provides an Apriori-based Product Recommendation engine for the TARIKA e-commerce platform. It generates "frequently bought together" association rules by analyzing customer purchase patterns from delivered orders.

## Architecture & Modularity
- **Completely Independent**: Reads only from `orders`, `order_items`, and `products`. Writes strictly to the existing `product_recommendations` database table.
- **Zero Impact on Other Modules**: Does not alter existing logic or schemas in `orders`, `catalog`, `warehouse`, `delivery`, `cart`, `accounts`, or `demand_prediction`.
- **Dynamic & Non-Hardcoded**: The recommendation rules update dynamically whenever the management command is triggered. If customer buying trends evolve, re-running the engine will mine new rules based on the latest delivered orders history.

## Apriori Recommendation Pipeline
1. **Data Source**: Delivers orders joined with order items and products:
   ```sql
   SELECT o.order_id, oi.product_id, p.product_name
   FROM orders o
   JOIN order_items oi ON o.order_id = oi.order_id
   JOIN products p ON oi.product_id = p.product_id
   WHERE o.order_status = 'delivered'
   ```
2. **Transaction Construction**: Each unique `order_id` is treated as a basket containing its set of distinct products.
3. **Transaction Encoding**: One-hot encoded using `mlxtend.preprocessing.TransactionEncoder`.
4. **Frequent Itemsets**: Mined using Apriori algorithm with `min_support = 0.002`.
5. **Association Rules**: Mined using `mlxtend.frequent_patterns.association_rules` on metric `confidence` (min_threshold=0.0).
6. **Directional Rules**: Filtered for 1-to-1 relations ($A \rightarrow B$). Support, confidence, and lift metrics are stored in `product_recommendations`.

## Management Command

To recalculate and refresh recommendations from the latest complete delivered-order history:

```bash
python manage.py update_recommendations
```

### Options:
- `--min-support <float>`: Customize the minimum support threshold (default: `0.002`).
- `--min-confidence <float>`: Customize the minimum confidence threshold (default: `0.0`).
- `--dry-run`: Mines and displays rules without modifying the database.

Example Output:
```
==================================================
RECOMMENDATION ENGINE SUMMARY
==================================================
Delivered orders / transactions : 5,756
Unique catalog products         : 187
Frequent itemsets mined         : 159
Recommendation rules produced   : 8
--------------------------------------------------
Status  : SUCCESS
Details : Successfully updated recommendation dataset with 8 rules.
==================================================
```

## API Endpoint

### `GET /api/recommendations/<product_id>/`
Public endpoint returning recommended products and association metrics for a given product.

#### Parameters:
- `product_id` (path parameter, UUID/string): The ID of the product.

#### Response (200 OK):
```json
{
  "product_id": "c529c4b3-366b-4eb2-a29b-329a1d063c47",
  "product_name": "Slim Fit T-Shirt",
  "category_id": "CAT-001",
  "total_recommendations": 2,
  "recommendations": [
    {
      "id": 2,
      "product": "Slim Fit T-Shirt",
      "frequently_bought_with": "Track Trousers",
      "support": 0.00243,
      "confidence": 0.0979,
      "lift": 3.079369,
      "recommended_product": {
        "product_id": "4fcae52a-7b59-43d6-b476-65dd33f6bb68",
        "product_name": "Track Trousers",
        "sku": "T-0167-980",
        "selling_price": 1010,
        "base_price": 1200,
        "category_id": "CAT-004",
        "category_name": "Bottom Wear",
        "gender": "Men",
        "color": "Black",
        "size": "L",
        "material": "Cotton Blend",
        "is_active": true
      }
    }
  ]
}
```

#### If Product Has No Recommendations:
Returns `200 OK` with an empty `recommendations` list:
```json
{
  "product_id": "some-product-id",
  "product_name": "Some Product",
  "category_id": "CAT-001",
  "total_recommendations": 0,
  "recommendations": []
}
```

#### If Product ID Does Not Exist:
Returns `404 Not Found`:
```json
{
  "detail": "Product with id \"xyz\" was not found."
}
```

## Testing

Run unit tests for the recommendations module:

```bash
python manage.py test recommendations
```
