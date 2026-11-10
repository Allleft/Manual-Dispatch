export function getDisplayPalletQuantity(order) {
  const pallets = Number(order.pallet_quantity || 0);
  return Number.isFinite(pallets) ? pallets : 0;
}

export function getLooseBagsQuantity(order) {
  const looseBags = Number(order.loose_bags_quantity || 0);
  return Number.isFinite(looseBags) ? looseBags : 0;
}

export function getCartonQuantity(order) {
  const cartons = Number(order.carton_quantity || 0);
  return Number.isFinite(cartons) ? cartons : 0;
}

export function getOrderLoadUnit(order) {
  if (getDisplayPalletQuantity(order) > 0) {
    return "PALLETS";
  }
  if (getLooseBagsQuantity(order) > 0) {
    return "BAGS";
  }
  if (getCartonQuantity(order) > 0) {
    return "CARTONS";
  }
  return "";
}

export function formatPluralLoadUnit(unit, quantity) {
  const normalized = String(unit || "").toUpperCase();
  const labels = {
    BAG: ["Bag", "Bags"],
    BAGS: ["Bag", "Bags"],
    CARTON: ["Carton", "Cartons"],
    CARTONS: ["Carton", "Cartons"],
    PALLET: ["Pallet", "Pallets"],
    PALLETS: ["Pallet", "Pallets"],
  };
  const [singular, plural] = labels[normalized] || [normalized, normalized];
  return Number(quantity) === 1 ? singular : plural;
}

export function formatOrderLoadQuantity(order) {
  const pallets = getDisplayPalletQuantity(order);
  const looseBags = getLooseBagsQuantity(order);
  const cartons = getCartonQuantity(order);
  return [
    pallets + " " + formatPluralLoadUnit("PALLETS", pallets),
    looseBags + " " + formatPluralLoadUnit("BAGS", looseBags),
    cartons + " " + formatPluralLoadUnit("CARTONS", cartons),
  ].join(" / ");
}

export function formatProductDetailLine(line, index) {
  const prefix = index === undefined || index === null ? "" : index + ". ";
  const productCode = String(line.product_code || "").trim();
  const productName = String(line.product_name || "").trim();
  const identity = [
    productCode ? "[" + productCode + "]" : "",
    productName,
  ].filter(Boolean).join(" ") || "Unnamed product";
  const quantity = Number(line.quantity || 0);
  const unit = String(line.unit || "").trim().toUpperCase();
  const packageQuantity = line.package_quantity;
  const packageUnit = String(line.package_unit || "").trim().toUpperCase();
  const packageText = packageQuantity !== null
    && packageQuantity !== undefined
    && packageQuantity !== ""
    && packageUnit
    ? " | Packaging: " + Number(packageQuantity) + " " + packageUnit
    : "";
  return (prefix + identity + " - " + quantity + " " + unit + packageText).trim();
}

function originalCartonizedBagQuantity(line) {
  const bags = Number(line.quantity);
  const identity = `${line.product_code || ""} ${line.product_name || ""}`;
  const weights = [...identity.matchAll(/(?<![0-9.])([0-9]+(?:\.[0-9]+)?)\s*KG\b/gi)]
    .map((match) => Number(match[1]));
  return ["BAG", "BAGS"].includes(String(line.unit || "").trim().toUpperCase())
    && String(line.package_unit || "").trim().toUpperCase() === "CARTON"
    && typeof line.quantity !== "boolean" && Number.isSafeInteger(bags) && bags > 0
    && weights.length > 0 && weights.every((weight) => weight === 1.5)
    ? bags : null;
}

export function getCartonizedInnerBagQuantity(line) {
  const bags = originalCartonizedBagQuantity(line);
  const cartons = Number(line.package_quantity);
  return bags !== null && typeof line.package_quantity !== "boolean"
    && Number.isSafeInteger(cartons) && cartons > 0 && bags === cartons * 14
    ? bags : null;
}

export function getDeliveryProductWeightKg(line) {
  const innerBags = originalCartonizedBagQuantity(line);
  if (innerBags !== null) return innerBags * 1.5;
  if (!["KG", "KGS"].includes(String(line.unit || "").toUpperCase())) return 0;
  const quantity = Number(line.quantity || 0);
  return Number.isFinite(quantity) ? quantity : 0;
}

export function formatDeliveryProductDetailLine(line, index) {
  if (getCartonizedInnerBagQuantity(line) === null) return formatProductDetailLine(line, index);
  const prefix = index === undefined || index === null ? "" : `${index}. `;
  const code = String(line.product_code || "").trim();
  const name = String(line.product_name || "").trim();
  const identity = [code ? `[${code}]` : "", name].filter(Boolean).join(" ");
  const cartons = Number(line.package_quantity);
  return `${prefix}${identity} - ${cartons} ${formatPluralLoadUnit("CARTON", cartons)}`;
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
