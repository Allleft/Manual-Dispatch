import { formatOptional } from "./format-utils.js";

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

export function createDetailField(label, value) {
  const field = document.createElement("div");
  field.className = "detail-field";

  const labelElement = document.createElement("dt");
  labelElement.textContent = label;

  const valueElement = document.createElement("dd");
  valueElement.textContent = formatOptional(value);

  field.append(labelElement, valueElement);
  return field;
}
