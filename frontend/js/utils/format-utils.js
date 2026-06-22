export function getDisplayPalletQuantity(order) {
  const pallets = Number(order.pallet_quantity || 0);
  return Number.isFinite(pallets) ? pallets : 0;
}

export function getLooseBagsQuantity(order) {
  const looseBags = Number(order.loose_bags_quantity || 0);
  return Number.isFinite(looseBags) ? looseBags : 0;
}

export function getOrderLoadUnit(order) {
  if (getDisplayPalletQuantity(order) > 0) {
    return "PALLETS";
  }
  if (getLooseBagsQuantity(order) > 0) {
    return "BAGS";
  }
  return "";
}

export function formatPluralLoadUnit(unit, quantity) {
  const normalized = String(unit || "").toUpperCase();
  const singular =
    normalized === "BAGS" ? "Bag" : normalized === "CARTONS" ? "Carton" : "Pallet";
  return Number(quantity) === 1 ? singular : `${singular}s`;
}

export function formatOrderLoadQuantity(order) {
  const pallets = getDisplayPalletQuantity(order);
  if (pallets > 0) {
    return `${pallets} ${formatPluralLoadUnit("PALLETS", pallets)}`;
  }

  const looseBags = getLooseBagsQuantity(order);
  if (looseBags > 0) {
    return `${looseBags} ${formatPluralLoadUnit("BAGS", looseBags)}`;
  }

  return "-";
}

export function formatProductDetailLine(line, index) {
  return `${index}. ${line.product_name || ""}    ${Number(line.quantity || 0)} ${formatPluralLoadUnit(
    line.unit,
    Number(line.quantity || 0),
  )}`;
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
