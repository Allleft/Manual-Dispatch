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
    body.classList.add("workspace-order-modal-body");
    const form = createDeliveryOrderForm(state, actions, formMode);
    const footer = form.querySelector(".workspace-modal-footer");
    footer?.remove();
    body.append(form);
    if (footer) {
      modal.querySelector(".workspace-modal")?.append(footer);
    }
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
      ["Invoice Date", order.invoice_date],
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
    createModalFactSection("Delivery Area", deliveryOrderAreaFacts(order)),
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
  if (order.delivery_area_source === "MANUAL") {
    row.append(createActionButton(
      "Reset to Automatic",
      () => actions.resetDeliveryOrderArea(order.order_id),
      {
        disabled: locked || isBusy(state, `delivery-area:${order.order_id}`),
        className: "workspace-modal-action-button workspace-modal-action-neutral",
      },
    ));
  }
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
      createBoundInput("Invoice Date", formState.invoice_date, (value) =>
        actions.updateDeliveryOrderForm("invoice_date", value), { type: "date" }),
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
        actions.updateDeliveryOrderForm("suburb", value), {
        onChange: actions.classifyDeliveryOrderForm,
      }),
      createBoundInput("Postcode", formState.postcode, (value) =>
        actions.updateDeliveryOrderForm("postcode", value), {
        onChange: actions.classifyDeliveryOrderForm,
      }),
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
    createDeliveryAreaFormSection(formState, actions, formMode),
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
        : "delivery-order-add")
        || formState.delivery_area_classification_pending
        || Boolean(formState.delivery_area_classification_error)
        || (formMode === "add"
          && formState.delivery_area_known === false
          && !formState.delivery_area_selection),
      primary: true,
      iconName: "document",
    }),
  );
  form.append(row);
  return form;
}

export function createDeliveryAreaFormSection(formState, actions, formMode) {
  const section = document.createElement("section");
  section.className = "workspace-form-section workspace-delivery-area-preview";
  const title = document.createElement("h4");
  title.textContent = "Delivery Area";
  section.append(title);
  if (formState.delivery_area_classification_pending) {
    section.append(createStatus("Determining Delivery Area...", "loading"));
    return section;
  }
  if (formState.delivery_area_classification_error) {
    section.append(createStatus(formState.delivery_area_classification_error, "error"));
    return section;
  }
  if (formState.delivery_area_known === null) {
    const helper = document.createElement("p");
    helper.className = "workspace-muted";
    helper.textContent = "Enter a suburb and postcode to determine the Delivery Area.";
    section.append(helper);
    return section;
  }
  const effectiveArea = formState.delivery_area_source === "MANUAL"
    ? formState.delivery_area
    : formState.auto_delivery_area;
  section.append(createModalFactSection("Classification", [
    ["Delivery Area", formatDeliveryArea(effectiveArea)],
    [
      "Area Source",
      formState.delivery_area_source === "MANUAL" ? "Manual Override" : "Automatic",
    ],
    ["Automatic Area", formatDeliveryArea(formState.auto_delivery_area)],
    ["Automatic Region", formatDeliveryRegion(formState.auto_delivery_region)],
  ]));
  if (formState.delivery_area_known === false) {
    section.append(createStatus(
      formMode === "add"
        ? "Delivery Area could not be determined. Choose an area before creating the Order."
        : "Delivery Area could not be determined. Saving this location will place the Order in Needs Area Review.",
      "error",
    ));
    if (formMode === "add") {
      section.append(createBoundSelect(
        "Delivery Area (required)",
        formState.delivery_area_selection || "",
        [
          { value: "", label: "Choose Delivery Area" },
          { value: "SOUTHEAST", label: "South East" },
          { value: "LOCAL", label: "Local" },
        ],
        (value) => actions.updateDeliveryOrderForm("delivery_area_selection", value),
      ));
    }
  }
  return section;
}

export function deliveryOrderAreaFacts(order) {
  const facts = [
    ["Delivery Area", formatDeliveryArea(order.delivery_area)],
    [
      "Area Source",
      order.delivery_area_source === "MANUAL" ? "Manual Override" : "Automatic",
    ],
  ];
  if (order.delivery_area_source === "MANUAL") {
    facts.push(["Automatic Area", formatDeliveryArea(order.auto_delivery_area)]);
  }
  facts.push(["Automatic Region", formatDeliveryRegion(order.auto_delivery_region)]);
  return facts;
}

export function formatDeliveryArea(area) {
  if (area === "SOUTHEAST") {
    return "South East";
  }
  if (area === "LOCAL") {
    return "Local";
  }
  return "Needs Area Review";
}

export function formatDeliveryRegion(region) {
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
  const columns = document.createElement("colgroup");
  [
    "sequence",
    "code",
    "name",
    "actual-quantity",
    "actual-unit",
    "packaging-quantity",
    "packaging-unit",
    "actions",
  ].forEach((name) => columns.append(createProductLineColumn(name)));
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
    row.className = "workspace-product-line-table-row";
    row.dataset.productLineId = line._draft_id;
    row.append(
      createProductLineCell(String(index + 1), "sequence"),
      createProductLineCell(createProductLineInput("Product code", line.product_code, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "product_code", value)), "code"),
      createProductLineCell(createProductLineInput("Product name", line.product_name, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "product_name", value)), "name"),
      createProductLineCell(createProductLineInput("Actual quantity", line.quantity, (value) => {
        line.quantity = value;
        actions.updateDeliveryOrderProductLine(line._draft_id, "quantity", value);
        total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
      }, "number"), "actual-quantity"),
      createProductLineCell(createProductLineInput("Actual unit", line.unit || "KG", (value) => {
        line.unit = value;
        actions.updateDeliveryOrderProductLine(line._draft_id, "unit", value);
        total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
      }), "actual-unit"),
      createProductLineCell(createProductLineInput("Packaging quantity", line.package_quantity, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "package_quantity", value), "number"), "packaging-quantity"),
      createProductLineCell(createProductLineInput("Packaging unit", line.package_unit, (value) =>
        actions.updateDeliveryOrderProductLine(line._draft_id, "package_unit", value)), "packaging-unit"),
      createProductLineCell(createActionButton("Remove product line", () =>
        actions.removeDeliveryOrderProductLine(line._draft_id), {
        iconName: "trash",
        iconOnly: true,
        accessibleLabel: `Remove product line ${index + 1}`,
        className: "workspace-product-line-remove",
      }), "actions"),
    );
    body.append(row);
  });
  table.append(columns, head, body);
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
  header.append(copy);
  const content = document.createElement("div");
  content.className = "workspace-load-product-layout";
  const load = document.createElement("section");
  load.className = "workspace-load-editor";
  const loadTitle = document.createElement("h5");
  loadTitle.textContent = "Load Summary";
  const loadDescription = document.createElement("p");
  loadDescription.textContent = "Review and update the delivery load quantities.";
  const loadFields = document.createElement("div");
  loadFields.className = "workspace-load-summary-fields";
  load.append(loadTitle, loadDescription, loadFields);
  [
    ["pallet_quantity", "Pallets"],
    ["loose_bags_quantity", "Loose Bags"],
    ["carton_quantity", "Cartons"],
  ].forEach(([field, label]) => {
    const control = createBoundInput(label, formState[field], (value) => {
      actions.updateDeliveryOrderForm(field, value);
    }, { type: "number" });
    control.classList.add("workspace-load-summary-field");
    loadFields.append(control);
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

function createProductLineColumn(name) {
  const column = document.createElement("col");
  column.className = `workspace-product-column-${name}`;
  return column;
}

function createProductLineCell(content, name) {
  const cell = document.createElement("td");
  cell.className = `workspace-product-cell-${name}`;
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
