import { formatOptional } from "./format-utils.js";
import { createIcon } from "./icon-utils.js";

export function createOption(value, label, selected = false) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  option.selected = selected;
  return option;
}

export function createBadge(text, variant = "neutral") {
  const badge = document.createElement("span");
  badge.className = `hint-badge hint-badge-${variant}`;
  badge.textContent = text;
  return badge;
}

export function createHint(text, variant = "neutral") {
  const hint = document.createElement("p");
  hint.className = `hint-row hint-row-${variant}`;
  hint.textContent = text;
  return hint;
}

export function createModalKicker(text, iconName = "document") {
  const kicker = document.createElement("p");
  kicker.className = "section-kicker modal-eyebrow";
  kicker.append(createIcon(iconName), document.createTextNode(text));
  return kicker;
}

export function setButtonContent(button, label, iconName = "", options = {}) {
  button.replaceChildren();
  if (!iconName) {
    button.textContent = label;
    return button;
  }

  const icon = createIcon(iconName);
  const text = document.createTextNode(label);
  if (options.iconAfter) {
    button.append(text, icon);
  } else {
    button.append(icon, text);
  }
  return button;
}

export function createDetailField(label, value) {
  const field = document.createElement("div");
  field.className = "detail-field";

  const icon = document.createElement("span");
  icon.className = "detail-field-icon";
  icon.append(createIcon(getDetailFieldIconName(label)));

  const content = document.createElement("span");
  content.className = "detail-field-content";

  const labelElement = document.createElement("dt");
  labelElement.textContent = label;

  const valueElement = document.createElement("dd");
  valueElement.textContent = formatOptional(value);

  content.append(labelElement, valueElement);
  field.append(icon, content);
  return field;
}

function getDetailFieldIconName(label) {
  const normalized = String(label || "").toLowerCase();
  if (normalized.includes("phone")) {
    return "phone";
  }
  if (
    normalized.includes("date") ||
    normalized.includes("day") ||
    normalized.includes("time") ||
    normalized.includes("frequency")
  ) {
    return "calendar";
  }
  if (
    normalized.includes("address") ||
    normalized.includes("suburb") ||
    normalized.includes("area") ||
    normalized.includes("postcode") ||
    normalized.includes("zone") ||
    normalized.includes("route group")
  ) {
    return "location";
  }
  if (normalized.includes("contact") || normalized.includes("driver") || normalized.includes("company")) {
    return "user";
  }
  if (normalized.includes("access") || normalized.includes("key")) {
    return "key";
  }
  if (normalized.includes("trailer") || normalized.includes("vehicle")) {
    return "truck";
  }
  if (normalized.includes("pallet") || normalized.includes("op shop") || normalized.includes("shop")) {
    return "store";
  }
  if (normalized.includes("bag")) {
    return "bag";
  }
  if (normalized.includes("status") || normalized.includes("run") || normalized.includes("generated")) {
    return "tag";
  }
  if (normalized.includes("invoice") || normalized.includes("note")) {
    return "document";
  }
  return "info";
}
