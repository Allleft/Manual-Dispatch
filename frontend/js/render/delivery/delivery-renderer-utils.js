import { createIcon } from "../../utils/icon-utils.js";

import {
  formatOptional,
  formatPluralLoadUnit,
} from "../../utils/format-utils.js";

export function ordersForDeliveryDate(board, deliveryDate) {
  return (board.orders || []).filter((order) => order.delivery_date === deliveryDate);
}

export function assignedOrdersForDriver(board, deliveryDate, driverId) {
  const orders = new Map((board.orders || []).map((order) => [order.order_id, order]));
  return (board.assignments || [])
    .filter((assignment) =>
      assignment.driver_id === driverId
    )
    .map((assignment) => ({ assignment, order: orders.get(assignment.task_id) }))
    .filter((item) => item.order?.delivery_date === deliveryDate)
    .sort((left, right) => {
      const tripCompare = (left.assignment.trip_no || "trip1").localeCompare(right.assignment.trip_no || "trip1");
      if (tripCompare) {
        return tripCompare;
      }
      return formatOptional(left.order.invoice_number, left.order.order_id).localeCompare(
        formatOptional(right.order.invoice_number, right.order.order_id),
      );
    });
}

export function findRunSheetForDriver(runSheets, deliveryDate, driverId) {
  return (runSheets || []).find(
    (runSheet) =>
      runSheet.delivery_date === deliveryDate &&
      runSheet.driver_id === driverId &&
      ["GENERATED", "SAVED"].includes(runSheet.status),
  );
}

export function findVehicleAssignment(board, deliveryDate, driverId) {
  return (board.driver_vehicle_assignments || []).find(
    (assignment) =>
      assignment.delivery_date === deliveryDate &&
      assignment.driver_id === driverId,
  );
}

export function assignmentMap(board) {
  return new Map(
    (board.assignments || []).map((assignment) => [assignment.task_id, assignment]),
  );
}

export function orderTotals(items) {
  return items.reduce(
    (totals, item) => ({
      pallets: totals.pallets + Number(item.order?.pallet_quantity || 0),
      bags: totals.bags + Number(item.order?.loose_bags_quantity || 0),
    }),
    { pallets: 0, bags: 0 },
  );
}

export function scopedDeliveryDate(state) {
  return state.deliveryTripSummaryDate || state.dispatchDate;
}

export function createSelect(labelText, value, options, onChange) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const select = document.createElement("select");
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  });
  select.value = value || "";
  select.addEventListener("change", () => onChange(select.value));
  label.append(text, select);
  return label;
}

export function createBoundInput(labelText, value, onInput, { type = "text" } = {}) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("input");
  input.type = type;
  if (type === "number") {
    input.setAttribute("min", "0");
  }
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  label.append(text, input);
  return label;
}

export function createBoundTextarea(labelText, value, onInput) {
  const label = document.createElement("label");
  label.className = "workspace-field workspace-field-wide";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("textarea");
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  label.append(text, input);
  return label;
}

export function createBoundSelect(labelText, value, options, onChange) {
  return createSelect(labelText, value, options, onChange);
}

export function createBoundCheckbox(labelText, checked, onChange) {
  const label = document.createElement("label");
  label.className = "workspace-field workspace-checkbox-field";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(checked);
  input.addEventListener("change", () => onChange(input.checked));
  label.append(input, document.createTextNode(labelText));
  return label;
}

export function createTextInput(labelText, value, placeholder, onInput, { type = "text" } = {}) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("input");
  input.type = type;
  input.value = value || "";
  input.placeholder = placeholder || "";
  input.addEventListener("input", () => onInput(input.value));
  label.append(text, input);
  return label;
}

export function createWorkspaceModal(titleText, onClose, {
  eyebrow = "Order Delivery",
  subtitle = "",
  iconName = "document",
  width = "order",
  closeDisabled = false,
} = {}) {
  const root = document.createElement("div");
  root.className = "workspace-modal-backdrop";
  const previouslyFocused = typeof document !== "undefined" ? document.activeElement : null;
  let closeRequested = false;
  const requestClose = () => {
    if (closeRequested) {
      return;
    }
    closeRequested = true;
    if (typeof document !== "undefined") {
      document.removeEventListener("keydown", handleDocumentEscape);
    }
    onClose();
    if (
      previouslyFocused
      && typeof previouslyFocused.focus === "function"
      && typeof window !== "undefined"
      && typeof window.requestAnimationFrame === "function"
    ) {
      window.requestAnimationFrame(() => {
        if (!document.body.contains(root) && document.body.contains(previouslyFocused)) {
          previouslyFocused.focus();
        }
      });
    }
  };
  const handleDocumentEscape = (event) => {
    if (event.key === "Escape" && !closeDisabled && document.body.contains(root)) {
      event.preventDefault();
      requestClose();
    }
  };
  if (typeof document !== "undefined") {
    document.addEventListener("keydown", handleDocumentEscape);
  }
  const modal = document.createElement("article");
  modal.className = `workspace-modal workspace-modal-${width}`;
  modal.tabIndex = -1;
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-label", titleText);
  modal.addEventListener("click", (event) => event.stopPropagation());
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !closeDisabled) {
      event.preventDefault();
      requestClose();
    }
    if (event.key === "Tab") {
      trapModalFocus(modal, event);
    }
  });
  const header = document.createElement("header");
  header.className = "workspace-modal-header";
  const titleGroup = document.createElement("div");
  titleGroup.className = "workspace-modal-title-group";
  const icon = document.createElement("span");
  icon.className = "workspace-modal-icon";
  icon.append(createIcon(iconName));
  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "workspace-modal-eyebrow";
  kicker.textContent = eyebrow;
  const title = document.createElement("h3");
  title.textContent = titleText;
  copy.append(kicker, title);
  if (subtitle) {
    const description = document.createElement("p");
    description.className = "workspace-modal-subtitle";
    description.textContent = subtitle;
    copy.append(description);
  }
  titleGroup.append(icon, copy);
  const close = createActionButton("Close", requestClose, {
    iconName: "x",
    className: "workspace-modal-close",
    iconOnly: true,
    accessibleLabel: "Close",
  });
  close.disabled = closeDisabled;
  header.append(titleGroup, close);
  const body = document.createElement("div");
  body.className = "workspace-modal-body";
  modal.append(header, body);
  root.append(modal);
  if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
    window.setTimeout(() => modal.focus(), 0);
  }
  return root;
}

export function trapModalFocus(modal, event) {
  const focusable = Array.from(
    modal.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"),
  );
  if (!focusable.length) {
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function createModalFactSection(titleText, facts) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createSectionHeading(titleText, ""));
  const list = document.createElement("dl");
  list.className = "workspace-fact-grid workspace-modal-fact-grid";
  facts.forEach(([labelText, value]) => appendFact(list, labelText, value));
  section.append(list);
  return section;
}

export function createFormSection(titleText, children) {
  const section = document.createElement("section");
  section.className = "workspace-form-section";
  const title = document.createElement("h4");
  title.textContent = titleText;
  const grid = document.createElement("div");
  grid.className = "workspace-form-grid";
  children.forEach((child) => grid.append(child));
  section.append(title, grid);
  return section;
}

export function createLoadSummary(order) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createSectionHeading("Load Summary", "Delivery totals remain Delivery Order only."));
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Pallet quantity", order.pallet_quantity);
  appendFact(facts, "Loose bag quantity", order.loose_bags_quantity);
  section.append(facts);
  return section;
}

export function isOrderCapturedByRunSheet(order, runSheets) {
  if (!order) {
    return false;
  }
  return (runSheets || []).some((runSheet) =>
    ["GENERATED", "SAVED"].includes(runSheet.status)
    && (runSheet.trips || []).some((trip) =>
      (trip.orders || []).some((snapshot) => snapshot.task_id === order.order_id),
    ),
  );
}

export function driverName(board, driverId) {
  if (!driverId) {
    return "No preferred driver";
  }
  return (board?.drivers || []).find((driver) => driver.driver_id === driverId)?.name || driverId;
}

export function createTableCell(content) {
  const cell = document.createElement("td");
  if (content && typeof content === "object" && typeof content.nodeType === "number") {
    cell.append(content);
  } else {
    cell.textContent = formatOptional(content, "");
  }
  return cell;
}

export function createTableHeader(labels) {
  const thead = document.createElement("thead");
  const row = document.createElement("tr");
  labels.forEach((labelText) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = labelText;
    row.append(cell);
  });
  thead.append(row);
  return thead;
}

export function createInlineInput(value, onInput, type = "text") {
  const input = document.createElement("input");
  input.type = type;
  if (type === "number") {
    input.setAttribute("min", "0");
  }
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  return input;
}

export function createInlineTextarea(value, onInput) {
  const input = document.createElement("textarea");
  input.className = "workspace-inline-textarea";
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  return input;
}

export function createInlineSelect(value, options, onChange) {
  const select = document.createElement("select");
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  });
  select.value = value || "";
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

export function createActionButton(label, onClick, {
  disabled = false,
  primary = false,
  iconName = "",
  className = "",
  iconOnly = false,
  accessibleLabel = "",
} = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = primary ? "button-primary workspace-action-button" : "button-secondary workspace-action-button";
  if (className) {
    button.className = `${button.className} ${className}`;
  }
  button.disabled = disabled;
  if (iconName) {
    button.append(createIcon(iconName));
  }
  if (iconOnly) {
    const description = accessibleLabel || label;
    button.setAttribute("aria-label", description);
    button.title = description;
  } else {
    button.append(document.createTextNode(label));
  }
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick(event);
  });
  return button;
}

export function createMetricGrid(metrics) {
  const grid = document.createElement("div");
  grid.className = "workspace-metric-grid workspace-metric-grid-delivery";
  metrics.forEach(([label, value, iconName]) => {
    const card = document.createElement("div");
    card.className = "workspace-metric-card";
    card.append(createIcon(iconName));
    const copy = document.createElement("div");
    const number = document.createElement("strong");
    number.textContent = String(value);
    const text = document.createElement("span");
    text.textContent = label;
    copy.append(number, text);
    card.append(copy);
    grid.append(card);
  });
  return grid;
}

export function createSectionHeading(titleText, descriptionText) {
  const heading = document.createElement("div");
  heading.className = "workspace-section-heading";
  const title = document.createElement("h3");
  title.textContent = titleText;
  const description = document.createElement("p");
  description.textContent = descriptionText;
  heading.append(title, description);
  return heading;
}

export function appendFact(list, labelText, value) {
  const item = document.createElement("div");
  const label = document.createElement("dt");
  label.textContent = labelText;
  const detail = document.createElement("dd");
  detail.textContent = formatOptional(value);
  item.append(label, detail);
  list.append(item);
}

export function createProductLines(order) {
  const products = document.createElement("section");
  products.className = "workspace-modal-section workspace-product-lines";
  const list = document.createElement("ul");
  (order.product_lines || []).forEach((line) => {
    const item = document.createElement("li");
    item.textContent = `${formatOptional(line.product_name)} - ${line.quantity} ${formatPluralLoadUnit(line.unit, line.quantity)}`;
    list.append(item);
  });
  if (!list.children.length) {
    const item = document.createElement("li");
    item.textContent = "No product lines recorded";
    list.append(item);
  }
  products.append(createSectionHeading("Product Lines", ""), list);
  return products;
}

export function createBadge(label, modifier = "") {
  const badge = document.createElement("span");
  badge.className = `workspace-badge${modifier ? ` workspace-badge-${modifier}` : ""}`;
  badge.textContent = label;
  return badge;
}

export function createChip(label) {
  const chip = document.createElement("span");
  chip.className = "workspace-chip";
  chip.textContent = label;
  return chip;
}

export function createStatus(message, type) {
  const status = document.createElement("p");
  status.className = `workspace-status workspace-status-${type}`;
  status.setAttribute(type === "error" ? "role" : "aria-live", type === "error" ? "alert" : "polite");
  status.textContent = message;
  return status;
}

export function createEmptyState(message, iconName) {
  const empty = document.createElement("div");
  empty.className = "workspace-empty-state";
  empty.append(createIcon(iconName));
  const text = document.createElement("p");
  text.textContent = message;
  empty.append(text);
  return empty;
}

export function formatLoad(order) {
  const pallets = Number(order.pallet_quantity || 0);
  const bags = Number(order.loose_bags_quantity || 0);
  return `${pallets} ${formatPluralLoadUnit("PALLETS", pallets)} - ${bags} ${formatPluralLoadUnit("BAGS", bags)}`;
}

export function isBusy(state, actionKey) {
  return Boolean(state.deliveryBusyActionKeys?.[actionKey]);
}
