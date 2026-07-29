import { formatOptional } from "../../utils/format-utils.js";

import {
  createBoundInput,
  createBoundTextarea,
  createBoundSelect,
  createWorkspaceModal,
  createModalFactSection,
  createFormSection,
  createLoadSummary,
  isOrderCapturedByRunSheet,
  driverName,
  createActionButton,
  createProductLines,
  createStatus,
  isBusy,
} from "./delivery-renderer-utils.js";

export function createDeliveryOrderModal(state, actions) {
  const formMode = state.deliveryOrderFormMode;
  const readOnly = Boolean(state.deliveryOrderDetailReadOnly);
  const board = deliveryModalBoard(state);
  const runSheets = deliveryModalRunSheets(state);
  const order = (board?.orders || []).find(
    (item) => item.order_id === state.deliveryOrderDetailId,
  );
  if (!formMode && !order) {
    return document.createDocumentFragment();
  }

  const modal = createWorkspaceModal(
    formMode === "add"
      ? "Add Delivery Order"
      : formMode === "edit"
        ? "Edit Delivery Order"
        : readOnly
          ? "Delivery Order Details"
          : `Delivery Order ${formatOptional(order?.invoice_number, order?.order_no)}`,
    actions.closeDeliveryOrderModal,
    {
      eyebrow: "Delivery Order",
      subtitle: formMode
        ? "Enter customer, delivery, load, product, and note details."
        : `${formatOptional(order?.company_name)}${order?.urgency ? ` - ${order.urgency}` : ""}`,
      iconName: "document",
      width: "order",
    },
  );
  const body = modal.querySelector(".workspace-modal-body");
  if (state.deliveryOrderModalError) {
    body.append(createStatus(state.deliveryOrderModalError, "error"));
  }

  if (formMode) {
    body.append(createDeliveryOrderForm(state, actions, formMode));
  } else {
    const locked = isOrderCapturedByRunSheet(order, runSheets);
    body.append(
      readOnly
        ? createDeliveryOrderReadOnlyActions(actions)
        : createDeliveryOrderActions(order, locked, state, actions),
      locked && !readOnly
        ? createStatus("This Delivery Order is captured by a Generated or Saved Delivery Run Sheet. Edit and Cancel are locked.", "loading")
        : document.createDocumentFragment(),
      createDeliveryOrderReadOnly(order, state, board),
    );
  }
  return modal;
}

export function deliveryModalBoard(state) {
  return state.workspaceRoute === "delivery/trip-summary"
    ? state.deliveryTripSummaryBoard || state.deliveryBoard
    : state.deliveryBoard;
}

export function deliveryModalRunSheets(state) {
  return state.workspaceRoute === "delivery/trip-summary"
    ? state.deliveryTripSummaryRunSheets || state.deliveryRunSheets
    : state.deliveryRunSheets;
}

export function createDeliveryOrderReadOnlyActions(actions) {
  const row = document.createElement("div");
  row.className = "workspace-modal-action-bar";
  row.append(
    createActionButton("Close", actions.closeDeliveryOrderModal, {
      className: "workspace-modal-action-button workspace-modal-action-neutral",
    }),
  );
  return row;
}

export function createDeliveryOrderReadOnly(order, state, board) {
  const fragment = document.createDocumentFragment();
  const assignmentFacts = deliveryOrderAssignmentFacts(order, board);
  fragment.append(
    createModalFactSection("General Information", [
      ["Invoice Number", order.invoice_number],
      ["Order Number", order.order_no],
      ["Company Name", order.company_name],
      ["Phone", order.phone],
      ["Preferred Driver", driverName(board, order.preferred_driver_id)],
    ]),
    createModalFactSection("Delivery Details", [
      ["Delivery Address", order.delivery_address],
      ["Suburb", order.suburb],
      ["Postcode", order.postcode],
      ["Delivery Date", order.delivery_date],
      ["Start Time", order.start_time],
      ["End Time", order.end_time],
      ["Zone", order.zone],
      ["Urgency", order.urgency],
    ]),
    assignmentFacts.length
      ? createModalFactSection("Current Assignment", assignmentFacts)
      : document.createDocumentFragment(),
    createLoadSummary(order),
    createProductLines(order),
    createModalFactSection("Notes", [["Notes", order.note]]),
  );
  return fragment;
}

export function deliveryOrderAssignmentFacts(order, board) {
  const assignment = (board?.assignments || []).find(
    (item) => item.task_type === "ORDER" && item.task_id === order.order_id,
  );
  if (!assignment) {
    return [];
  }
  return [
    ["Current assigned driver", driverName(board, assignment.driver_id)],
    ["Current trip", assignment.trip_no === "trip2" ? "Trip 2" : "Trip 1"],
  ];
}

export function createDeliveryOrderActions(order, locked, state, actions) {
  const row = document.createElement("div");
  row.className = "workspace-modal-action-bar";
  row.append(
    createActionButton("Close", actions.closeDeliveryOrderModal, {
      className: "workspace-modal-action-button workspace-modal-action-neutral",
    }),
    createActionButton("Edit Order", () => actions.startEditDeliveryOrder(order.order_id), {
      disabled: locked || isBusy(state, `delivery-order-edit:${order.order_id}`),
      primary: true,
      iconName: "edit",
      className: "workspace-modal-action-button workspace-modal-action-primary",
    }),
    createActionButton("Cancel Order", () => actions.cancelActiveDeliveryOrder(order.order_id), {
      disabled: locked || isBusy(state, `delivery-order-cancel:${order.order_id}`),
      iconName: "trash",
      className: "workspace-modal-action-button workspace-modal-action-danger",
    }),
  );
  return row;
}

export function createDeliveryOrderForm(state, actions, formMode) {
  const form = document.createElement("form");
  form.className = "workspace-modal-section workspace-order-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    actions.saveDeliveryOrderForm();
  });
  const formState = state.deliveryOrderForm || {};
  form.append(
    createFormSection("Customer Information", [
      createBoundInput("Invoice Number", formState.invoice_number, (value) =>
        actions.updateDeliveryOrderForm("invoice_number", value)),
      createBoundInput("Order Number", formState.order_no, (value) =>
        actions.updateDeliveryOrderForm("order_no", value)),
      createBoundInput("Company Name", formState.company_name, (value) =>
        actions.updateDeliveryOrderForm("company_name", value)),
      createBoundInput("Phone", formState.phone, (value) =>
        actions.updateDeliveryOrderForm("phone", value)),
    ]),
    createFormSection("Delivery Requirements", [
      createBoundInput("Delivery Address", formState.delivery_address, (value) =>
        actions.updateDeliveryOrderForm("delivery_address", value)),
      createBoundInput("Suburb", formState.suburb, (value) =>
        actions.updateDeliveryOrderForm("suburb", value)),
      createBoundInput("Postcode", formState.postcode, (value) =>
        actions.updateDeliveryOrderForm("postcode", value)),
      createBoundInput("Delivery Date", formState.delivery_date, (value) =>
        actions.updateDeliveryOrderForm("delivery_date", value), { type: "date" }),
      createBoundInput("Start Time", formState.start_time, (value) =>
        actions.updateDeliveryOrderForm("start_time", value), { type: "time" }),
      createBoundInput("End Time", formState.end_time, (value) =>
        actions.updateDeliveryOrderForm("end_time", value), { type: "time" }),
      createBoundInput("Zone", formState.zone, (value) =>
        actions.updateDeliveryOrderForm("zone", value)),
      createBoundSelect("Urgency", formState.urgency || "Normal", [
        { value: "Normal", label: "Normal" },
        { value: "Urgent", label: "Urgent" },
      ], (value) => actions.updateDeliveryOrderForm("urgency", value)),
      createBoundSelect("Preferred Driver", formState.preferred_driver_id || "", [
        { value: "", label: "No preferred driver" },
        ...((state.deliveryBoard?.drivers || []).map((driver) => ({
          value: driver.driver_id,
          label: driver.name,
        }))),
      ], (value) => actions.updateDeliveryOrderForm("preferred_driver_id", value)),
    ]),
    createLoadAndProductLinesSection(formState, actions),
    createFormSection("Notes", [
      createBoundTextarea("Notes", formState.note || "", (value) =>
        actions.updateDeliveryOrderForm("note", value)),
    ]),
  );
  const row = document.createElement("footer");
  row.className = "workspace-modal-footer";
  row.append(
    createActionButton("Cancel", formMode === "edit"
      ? actions.cancelDeliveryOrderEdit
      : actions.closeDeliveryOrderModal),
    createActionButton(formMode === "edit" ? "Save Changes" : "Create Order", () => actions.saveDeliveryOrderForm(), {
      disabled: isBusy(state, formMode === "edit"
        ? `delivery-order-edit:${state.deliveryOrderDetailId}`
        : "delivery-order-add"),
      primary: true,
      iconName: "document",
    }),
  );
  form.append(row);
  return form;
}

export function createProductLineEditor(lines, actions) {
  const section = document.createElement("section");
  section.className = "workspace-product-line-editor";
  const heading = document.createElement("div");
  heading.className = "workspace-load-product-heading";
  const title = document.createElement("h5");
  title.textContent = `Product Lines (${lines.length})`;
  heading.append(title, createActionButton("Add Product Line", actions.addDeliveryOrderProductLine, {
    iconName: "plus",
    className: "workspace-product-line-add",
  }));
  const scroll = document.createElement("div");
  scroll.className = "workspace-product-line-table-scroll";
  scroll.tabIndex = 0;
  scroll.setAttribute("aria-label", "Editable product lines");
  const table = document.createElement("table");
  table.className = "workspace-product-line-table";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["#", "Product Code", "Product Name", "Actual Quantity", "Actual Unit", "Packaging Quantity", "Packaging Unit", "Actions"]
    .forEach((label) => {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      headRow.append(cell);
    });
  head.append(headRow);
  const body = document.createElement("tbody");
  const total = document.createElement("p");
  total.className = "workspace-product-line-total";
  (lines || []).forEach((line, index) => {
    const row = document.createElement("tr");
    row.className = "workspace-product-line-row";
    row.dataset.productLineId = line._draft_id;
    row.append(
      createProductLineCell(String(index + 1)),
      createProductLineCell(createProductLineInput("Product code", line.product_code, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "product_code", value))),
      createProductLineCell(createProductLineInput("Product name", line.product_name, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "product_name", value))),
      createProductLineCell(createProductLineInput("Actual quantity", line.quantity, (value) => {
        line.quantity = value;
        actions.updateDeliveryOrderProductLine(line._draft_id, "quantity", value);
        total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
      }, "number")),
      createProductLineCell(createProductLineInput("Actual unit", line.unit || "KG", (value) => {
        line.unit = value;
        actions.updateDeliveryOrderProductLine(line._draft_id, "unit", value);
        total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
      })),
      createProductLineCell(createProductLineInput("Packaging quantity", line.package_quantity, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "package_quantity", value), "number")),
      createProductLineCell(createProductLineInput("Packaging unit", line.package_unit, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "package_unit", value))),
      createProductLineCell(createActionButton("Remove product line", () =>
        actions.removeDeliveryOrderProductLine(line._draft_id), {
        iconName: "trash",
        iconOnly: true,
        accessibleLabel: `Remove product line ${index + 1}`,
        className: "workspace-product-line-remove",
      })),
    );
    body.append(row);
  });
  table.append(head, body);
  scroll.append(table);
  total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
  section.append(heading, scroll, total);
  return section;
}

export function createLoadAndProductLinesSection(formState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-form-section workspace-load-product-section";
  const header = document.createElement("div");
  header.className = "workspace-load-product-header";
  const copy = document.createElement("div");
  const title = document.createElement("h4");
  title.textContent = "Load and Product Lines";
  const subtitle = document.createElement("p");
  subtitle.textContent = "Review load quantities and product details before saving.";
  copy.append(title, subtitle);
  const metrics = document.createElement("div");
  metrics.className = "workspace-load-metrics";
  const metricValues = {};
  [
    ["pallet_quantity", "Pallets"],
    ["loose_bags_quantity", "Loose Bags"],
    ["carton_quantity", "Cartons"],
  ].forEach(([field, label]) => {
    const card = document.createElement("span");
    const value = document.createElement("strong");
    value.textContent = String(formState[field] || 0);
    const text = document.createElement("small");
    text.textContent = label;
    card.append(value, text);
    metrics.append(card);
    metricValues[field] = value;
  });
  header.append(copy, metrics);
  const content = document.createElement("div");
  content.className = "workspace-load-product-layout";
  const load = document.createElement("section");
  load.className = "workspace-load-editor";
  const loadTitle = document.createElement("h5");
  loadTitle.textContent = "Load Summary";
  load.append(loadTitle);
  [
    ["pallet_quantity", "Pallets"],
    ["loose_bags_quantity", "Loose Bags"],
    ["carton_quantity", "Cartons"],
  ].forEach(([field, label]) => {
    load.append(createBoundInput(label, formState[field], (value) => {
      actions.updateDeliveryOrderForm(field, value);
      metricValues[field].textContent = value || "0";
    }, { type: "number" }));
  });
  content.append(load, createProductLineEditor(formState.product_lines || [], actions));
  section.append(header, content);
  return section;
}

function createProductLineInput(label, value, onInput, type = "text") {
  const input = document.createElement("input");
  input.type = type;
  input.setAttribute("aria-label", label);
  if (type === "number") {
    input.setAttribute("min", "0");
  }
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  return input;
}

function createProductLineCell(content) {
  const cell = document.createElement("td");
  if (content?.nodeType) {
    cell.append(content);
  } else {
    cell.textContent = content;
  }
  return cell;
}

export function formatProductLineTotals(lines) {
  const totals = new Map();
  (lines || []).forEach((line) => {
    const unit = String(line.unit || "unit").trim().toUpperCase() || "UNIT";
    totals.set(unit, (totals.get(unit) || 0) + Number(line.quantity || 0));
  });
  return [...totals.entries()].map(([unit, quantity]) => `${quantity} ${unit}`).join(" · ") || "0";
}
