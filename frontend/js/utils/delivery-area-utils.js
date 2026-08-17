export const DELIVERY_AREA_REVIEW_WARNING =
  "Delivery area could not be determined from suburb/postcode. Needs Review.";

export function applyDeliveryAreaClassification(row, classification) {
  const warnings = (row.warnings || []).filter(
    (warning) => warning !== DELIVERY_AREA_REVIEW_WARNING,
  );
  if (!classification.known) {
    warnings.push(DELIVERY_AREA_REVIEW_WARNING);
  }
  return {
    ...row,
    auto_delivery_region: classification.auto_delivery_region ?? null,
    auto_delivery_area: classification.auto_delivery_area ?? null,
    delivery_area_override: null,
    delivery_area: classification.delivery_area ?? null,
    delivery_area_source: "AUTO",
    warnings,
  };
}

export function formatDeliveryAreaLabel(area) {
  if (area === "SOUTHEAST") {
    return "South East";
  }
  if (area === "LOCAL") {
    return "Local";
  }
  return "Needs Review";
}

export function formatDeliveryRegionLabel(region) {
  const labels = {
    SOUTHEAST: "South East",
    SOUTHWEST: "South West",
    EAST: "East",
    SOUTH: "South",
    NORTH: "North",
    CITY: "City",
    WEST: "West",
  };
  return labels[region] || "Needs Review";
}
