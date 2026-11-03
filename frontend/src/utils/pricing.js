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

  const basePrice = Math.max(
    0,
    toFiniteNumber(product.base_price ?? product.initial_price ?? product.actual_price) ?? 0
  );

  const discountedPrice = toFiniteNumber(product.discounted_price);
  const sellingPrice = toFiniteNumber(product.selling_price ?? product.sale_price);
  const discountVal = toFiniteNumber(product.discount_amount ?? product.discount_price);

  let currentPrice;
  let discountAmount = 0;

  if (discountedPrice != null && discountedPrice > 0) {
    currentPrice = discountedPrice;
    discountAmount = basePrice > currentPrice
      ? Math.round((basePrice - currentPrice) * 100) / 100
      : (discountVal || 0);
  } else if (sellingPrice != null && sellingPrice > 0) {
    // Guard: If sellingPrice is identical to discountVal (e.g. 100 when base is 1988)
    // then 100 is the discount amount to be reduced from basePrice
    if (basePrice > 0 && discountVal != null && Math.abs(sellingPrice - discountVal) < 0.01 && (basePrice - discountVal) > 0) {
      currentPrice = Math.round((basePrice - discountVal) * 100) / 100;
      discountAmount = discountVal;
    } else {
      currentPrice = sellingPrice;
      discountAmount = basePrice > currentPrice
        ? Math.round((basePrice - currentPrice) * 100) / 100
        : (discountVal || 0);
    }
  } else if (discountVal != null && basePrice > 0) {
    currentPrice = Math.max(0, Math.round((basePrice - discountVal) * 100) / 100);
    discountAmount = discountVal;
  } else {
    currentPrice = basePrice;
    discountAmount = 0;
  }

  // Percentage beside the discounted price: amount / original * 100, max 2 dp.
  const discountPercentage = basePrice > 0 && discountAmount > 0
    ? Math.round((discountAmount / basePrice) * 100 * 100) / 100
    : 0;

  return {
    basePrice,
    currentPrice,
    discountAmount,
    discountPercentage,
    isOnSale: discountAmount > 0 && currentPrice < basePrice,
  };
}

// "20% OFF" formatting: up to 2 decimals with trailing zeros trimmed.
export function formatDiscountPercentage(percentage) {
  const value = Number(percentage);
  if (!Number.isFinite(value) || value <= 0) return '0%';
  return `${parseFloat(value.toFixed(2))}%`;
}
