export function getDisplayPalletQuantity(order) {
  const pallets = Number(order.pallet_quantity || 0);
  return Number.isFinite(pallets) ? pallets : 0;
}

export function getLooseBagsQuantity(order) {
  const looseBags = Number(order.loose_bags_quantity || 0);
  return Number.isFinite(looseBags) ? looseBags : 0;
}

export function formatOptional(value, fallback = "-") {
  return value === undefined || value === null || value === "" ? fallback : value;
}

export function truncateText(value, maxLength = 44) {
  const text = String(value || "");
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}...`;
}

export function normalizeSearchText(value) {
  return String(value || "").trim().toLowerCase();
}

export function isUrgent(order) {
  return String(order.urgency || "").toLowerCase() === "urgent";
}

export function getUrgencyLabel(order) {
  const urgency = order.urgency || "Normal";
  return urgency.charAt(0).toUpperCase() + urgency.slice(1).toLowerCase();
}
