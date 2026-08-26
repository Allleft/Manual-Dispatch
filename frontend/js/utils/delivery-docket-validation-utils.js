const REQUIRED_WARNING_RULES = Object.freeze([
  ["docket_number", "Delivery Docket number was not found."],
  ["company_name", "Customer company was not found."],
  ["delivery_address", "Deliver To street address was not found."],
  ["suburb", "Deliver To suburb was not found."],
  ["delivery_date", "Delivery date was not resolved."],
]);

const LOAD_WARNING = "No pallet, loose bag, or carton load was found.";
const INVALID_LOAD_WARNING = "Delivery load quantities must be whole non-negative numbers.";
const DUPLICATE_WARNING = "Duplicate invoice number already exists.";
const FRACTIONAL_PRODUCT_WARNING_PREFIX = "Product actual quantity is fractional (";
const INVALID_PRODUCT_WARNING = "Product line data is invalid and must be corrected before import.";
const PRODUCT_CODE_PATTERN = /^[A-Z0-9][A-Z0-9./_-]*$/;

const MANAGED_EXACT_WARNINGS = new Set([
  ...REQUIRED_WARNING_RULES.map(([_field, warning]) => warning),
  LOAD_WARNING,
  INVALID_LOAD_WARNING,
  DUPLICATE_WARNING,
  INVALID_PRODUCT_WARNING,
]);

export function revalidateDeliveryDocketRow(row) {
  const productWarnings = deliveryDocketProductWarnings(row.product_lines);
  const requiredWarnings = REQUIRED_WARNING_RULES
    .filter(([field]) => !hasText(row[field]))
    .map(([_field, warning]) => warning);
  const loadWarnings = deliveryDocketLoadWarnings(row);
  const duplicateWarnings = row.is_duplicate ? [DUPLICATE_WARNING] : [];
  const blockingWarnings = unique([
    ...productWarnings,
    ...requiredWarnings,
    ...loadWarnings,
    ...duplicateWarnings,
  ]);
  const unmanagedWarnings = (row.warnings || []).filter(
    (warning) => !isManagedValidationWarning(warning),
  );
  const warnings = unique([
    ...productWarnings,
    ...unmanagedWarnings,
    ...requiredWarnings,
    ...loadWarnings,
    ...duplicateWarnings,
  ]);
  const importable = blockingWarnings.length === 0;
  return {
    ...row,
    warnings,
    importable,
    selected: Boolean(row.selected && importable),
  };
}

function deliveryDocketLoadWarnings(row) {
  const quantities = [
    row.pallet_quantity,
    row.loose_bags_quantity,
    row.carton_quantity,
  ].map(normalizeOptionalWholeQuantity);
  if (quantities.some((quantity) => quantity === null)) {
    return [INVALID_LOAD_WARNING];
  }
  if (!quantities.some((quantity) => quantity > 0)) {
    return [LOAD_WARNING];
  }
  return [];
}

function deliveryDocketProductWarnings(productLines) {
  if (productLines === null || productLines === undefined || productLines === "") {
    return [];
  }
  if (!Array.isArray(productLines)) {
    return [INVALID_PRODUCT_WARNING];
  }
  const fractionalWarnings = [];
  let hasOtherInvalidCondition = false;
  productLines.forEach((line) => {
    if (!line || typeof line !== "object" || Array.isArray(line)) {
      hasOtherInvalidCondition = true;
      return;
    }
    const numericQuantity = numericValue(line.quantity);
    if (numericQuantity !== null && !Number.isInteger(numericQuantity)) {
      fractionalWarnings.push(
        `${FRACTIONAL_PRODUCT_WARNING_PREFIX}${numericQuantity} KG) and cannot be imported safely.`,
      );
    } else if (!Number.isSafeInteger(numericQuantity) || numericQuantity <= 0) {
      hasOtherInvalidCondition = true;
    }
    if (!hasText(line.product_name || line.description)) {
      hasOtherInvalidCondition = true;
    }
    if (!isBoundedProductCode(line.unit, 20, true)
        || !isBoundedProductCode(line.product_code, 40, false)) {
      hasOtherInvalidCondition = true;
    }
    const hasPackageQuantity = hasText(line.package_quantity);
    const hasPackageUnit = hasText(line.package_unit);
    if (hasPackageQuantity !== hasPackageUnit) {
      hasOtherInvalidCondition = true;
    } else if (hasPackageQuantity
        && (normalizeOptionalWholeQuantity(line.package_quantity) === null
          || !isBoundedProductCode(line.package_unit, 20, true))) {
      hasOtherInvalidCondition = true;
    }
  });
  return unique([
    ...fractionalWarnings,
    ...(hasOtherInvalidCondition ? [INVALID_PRODUCT_WARNING] : []),
  ]);
}

function normalizeOptionalWholeQuantity(value) {
  if (value === null || value === undefined || value === "") {
    return 0;
  }
  const quantity = numericValue(value);
  if (!Number.isSafeInteger(quantity) || quantity < 0) {
    return null;
  }
  return quantity;
}

function numericValue(value) {
  if (typeof value === "boolean" || !hasText(value)) {
    return null;
  }
  const quantity = Number(value);
  return Number.isFinite(quantity) ? quantity : null;
}

function isBoundedProductCode(value, maxLength, required) {
  const text = String(value ?? "").trim().toUpperCase();
  if (!text) {
    return !required;
  }
  return text.length <= maxLength && PRODUCT_CODE_PATTERN.test(text);
}

function isManagedValidationWarning(warning) {
  const text = String(warning || "");
  return MANAGED_EXACT_WARNINGS.has(text)
    || text.startsWith(FRACTIONAL_PRODUCT_WARNING_PREFIX);
}

function hasText(value) {
  return String(value ?? "").trim().length > 0;
}

function unique(values) {
  return [...new Set(values)];
}
