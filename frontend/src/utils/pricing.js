export function getProductPricing(product = {}) {
  const basePrice = Math.max(0, Number(product.base_price || product.selling_price || 0) || 0);
  const listedPriceValue = product.sale_price ?? product.selling_price;
  const listedPrice = Number(listedPriceValue);
  const hasListedPrice = listedPriceValue != null && Number.isFinite(listedPrice);
  const suppliedDiscount = Number(product.discount_percentage);
  const discountAmount = Number.isFinite(suppliedDiscount) && suppliedDiscount > 0
    ? suppliedDiscount
    : hasListedPrice && listedPrice < basePrice
      ? basePrice - listedPrice
      : 0;
  const currentPrice = discountAmount > 0
    ? Math.max(0, basePrice - discountAmount)
    : hasListedPrice
      ? listedPrice
      : basePrice;

  return {
    basePrice,
    currentPrice,
    discountAmount,
    isOnSale: discountAmount > 0,
  };
}