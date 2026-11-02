// Pricing helper shared by the customer cards, the product modal and the
// warehouse UI. Backend field semantics (public.products):
//   base_price      -> original price (`initial_price` column)
//   selling_price   -> FINAL discounted selling price (`actual_price` TEXT)
//   discount_price  -> discount AMOUNT in currency, never a percentage
// The percentage is always derived here (or by Django), never stored.
export function getProductPricing(product = {}) {
  const toFiniteNumber = (value) => {
    if (value === null || value === undefined || value === '') return null;
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  };

  const basePrice = Math.max(0, toFiniteNumber(product.base_price ?? product.initial_price) ?? 0);

  // Final selling price as delivered by the API ('800' text or number).
  const listedPriceValue = product.sale_price ?? product.selling_price ?? product.actual_price;
  const listedPrice = toFiniteNumber(listedPriceValue);

  // Discount AMOUNT in currency (products.discount_price); legacy payloads
  // may still carry discount_percentage — treat it as a percentage hint only.
  const suppliedAmount = toFiniteNumber(product.discount_price);
  let discountAmount = suppliedAmount != null && suppliedAmount >= 0 ? suppliedAmount : 0;
  if (suppliedAmount == null && listedPrice != null && listedPrice < basePrice) {
    discountAmount = basePrice - listedPrice;
  }

  // Current price: prefer the delivered final price; fall back to
  // base - discount so older payloads (without actual_price) still render.
  let currentPrice;
  if (listedPrice != null) {
    currentPrice = listedPrice;
  } else {
    currentPrice = Math.max(0, basePrice - discountAmount);
  }

  // Percentage beside the discounted price: amount / original * 100, max 2 dp.
  // A zero / missing original price is handled safely (no division).
  const discountPercentage = basePrice > 0
    ? Math.round((discountAmount / basePrice) * 100 * 100) / 100
    : 0;

  return {
    basePrice,
    currentPrice,
    discountAmount,
    discountPercentage,
    isOnSale: discountAmount > 0,
  };
}

// "20% OFF" formatting: up to 2 decimals with trailing zeros trimmed.
export function formatDiscountPercentage(percentage) {
  const value = Number(percentage);
  if (!Number.isFinite(value) || value <= 0) return '0%';
  return `${parseFloat(value.toFixed(2))}%`;
}
