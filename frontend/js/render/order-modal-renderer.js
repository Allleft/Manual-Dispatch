import { state } from "../state/app-state.js";
import {
  getOrderByTaskId,
  getOrderPreferredDriverName,
} from "../state/selectors.js";
import {
  createDetailField,
  createOption,
} from "../utils/dom-utils.js";
import {
  formatOptional,
  getDisplayPalletQuantity,
  getLooseBagsQuantity,
  getUrgencyLabel,
} from "../utils/format-utils.js";

export function renderAddOrderPopup({
  onCloseAddOrder,
  onCreateOrder,
  onUpdateAddOrderForm,
}) {
  const root = document.querySelector("#add-order-root");
  if (!root) {
    return;
  }

  root.innerHTML = "";
  if (!state.isAddOrderOpen) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop";

  const modal = document.createElement("article");
  modal.className = "order-detail-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "add-order-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Manual entry";

  const title = document.createElement("h2");
  title.id = "add-order-title";
  title.textContent = "Add New Order";

  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  closeButton.textContent = "Cancel";
  closeButton.disabled = state.isSaving;
  closeButton.addEventListener("click", onCloseAddOrder);

  header.append(titleWrap, closeButton);

  const form = document.createElement("form");
  form.className = "order-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    onCreateOrder();
  });

  const formGrid = document.createElement("div");
  formGrid.className = "form-grid";

  const preferredDriverOptions = [
    { value: "", label: "No preferred driver" },
    ...state.drivers.map((driver) => ({
      value: driver.driver_id,
      label: driver.name,
    })),
  ];

  formGrid.append(
    createAddOrderField("Invoice #", "invoice_number", { onUpdateAddOrderForm }),
    createAddOrderField("Company Name", "company_name", { onUpdateAddOrderForm }),
    createAddOrderField("Phone", "phone", { type: "tel", onUpdateAddOrderForm }),
    createAddOrderField("Delivery Address", "delivery_address", { onUpdateAddOrderForm }),
    createAddOrderField("Suburb", "suburb", { required: true, onUpdateAddOrderForm }),
    createAddOrderField("Postcode", "postcode", { onUpdateAddOrderForm }),
    createAddOrderField("Delivery Date", "delivery_date", {
      type: "date",
      required: true,
      onUpdateAddOrderForm,
    }),
    createAddOrderField("Zone", "zone", { onUpdateAddOrderForm }),
    createAddOrderSelect("Urgency", "urgency", [
      { value: "Normal", label: "Normal" },
      { value: "Urgent", label: "Urgent" },
    ], { onUpdateAddOrderForm }),
    createAddOrderSelect("Preferred Driver", "preferred_driver_id", preferredDriverOptions, {
      onUpdateAddOrderForm,
    }),
    createAddOrderField("Pallet Quantity", "pallet_quantity", {
      type: "number",
      min: "0",
      onUpdateAddOrderForm,
    }),
    createAddOrderField("Loose Bags Quantity", "loose_bags_quantity", {
      type: "number",
      min: "0",
      onUpdateAddOrderForm,
    }),
    createAddOrderField("Start Time", "start_time", { type: "time", onUpdateAddOrderForm }),
    createAddOrderField("End Time", "end_time", { type: "time", onUpdateAddOrderForm }),
    createAddOrderField("Note", "note", {
      multiline: true,
      wide: true,
      onUpdateAddOrderForm,
    }),
  );

  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.addOrderError;
  error.textContent = state.addOrderError;

  const actions = document.createElement("div");
  actions.className = "form-actions";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "button-secondary";
  cancelButton.textContent = "Cancel";
  cancelButton.disabled = state.isSaving;
  cancelButton.addEventListener("click", onCloseAddOrder);

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.textContent = state.isSaving ? "Saving..." : "Save Order";
  saveButton.disabled = state.isSaving;

  actions.append(cancelButton, saveButton);
  form.append(formGrid, error, actions);
  modal.append(header, form);
  backdrop.append(modal);
  root.append(backdrop);
}

export function renderOrderDetailPopup({
  getOrderEditForm,
  onCancelOrder,
  onCancelOrderEdit,
  onCloseOrderDetail,
  onSaveOrderEdit,
  onStartOrderEdit,
  onUpdateOrderEditForm,
}) {
  let root = document.querySelector("#order-detail-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "order-detail-root";
    document.body.append(root);
  }

  root.innerHTML = "";
  if (!state.activeOrderDetailId) {
    return;
  }

  const order = getOrderByTaskId(state.activeOrderDetailId);
  if (!order) {
    state.activeOrderDetailId = "";
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop";

  const modal = document.createElement("article");
  modal.className = "order-detail-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "order-detail-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Order details";

  const title = document.createElement("h2");
  title.id = "order-detail-title";
  title.textContent = `${formatOptional(order.invoice_number)} - ${formatOptional(order.suburb)}`;

  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  closeButton.textContent = "Close";
  closeButton.addEventListener("click", onCloseOrderDetail);

  const headerActions = document.createElement("div");
  headerActions.className = "detail-actions";

  if (!state.isOrderEditMode) {
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => onStartOrderEdit(order));

    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "button-danger";
    cancelButton.textContent = state.isSaving ? "Cancelling..." : "Cancel Order";
    cancelButton.disabled = state.isSaving;
    cancelButton.addEventListener("click", () => onCancelOrder(order.order_id));

    headerActions.append(editButton, cancelButton);
  }

  headerActions.append(closeButton);

  header.append(titleWrap, headerActions);

  if (state.isOrderEditMode && Object.keys(state.orderEditForm).length === 0) {
    state.orderEditForm = getOrderEditForm(order);
  }

  if (state.isOrderEditMode) {
    modal.append(
      header,
      createOrderEditForm(order, {
        onCancelOrderEdit,
        onSaveOrderEdit,
        onUpdateOrderEditForm,
      }),
    );
    backdrop.append(modal);
    root.append(backdrop);
    return;
  }

  const details = document.createElement("dl");
  details.className = "detail-grid";
  details.append(
    createDetailField("Order ID", order.order_id),
    createDetailField("Invoice #", order.invoice_number),
    createDetailField("Company Name", order.company_name),
    createDetailField("Phone", order.phone),
    createDetailField("Delivery Address", order.delivery_address),
    createDetailField("Suburb", order.suburb),
    createDetailField("Postcode", order.postcode),
    createDetailField("Delivery Date", order.delivery_date),
    createDetailField("Zone", order.zone),
    createDetailField("Urgency", getUrgencyLabel(order)),
    createDetailField("Preferred Driver", getOrderPreferredDriverName(order)),
    createDetailField("Pallet Quantity", getDisplayPalletQuantity(order)),
    createDetailField("Loose Bags Quantity", getLooseBagsQuantity(order)),
    createDetailField("Start Time", order.start_time),
    createDetailField("End Time", order.end_time),
    createDetailField("Note", order.note),
  );

  const detailError = document.createElement("p");
  detailError.className = "board-error";
  detailError.hidden = !state.errorMessage;
  detailError.textContent = state.errorMessage;

  modal.append(header, detailError, details);
  backdrop.append(modal);
  root.append(backdrop);
}

function createAddOrderField(label, field, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = options.wide ? "form-field form-field-wide" : "form-field";
  wrapper.textContent = label;

  const input = document.createElement(options.multiline ? "textarea" : "input");
  input.name = field;
  input.value = state.addOrderForm[field] ?? "";
  input.disabled = state.isSaving;
  if (!options.multiline) {
    input.type = options.type || "text";
  }
  if (options.required) {
    input.required = true;
  }
  if (options.min !== undefined) {
    input.min = options.min;
  }
  input.addEventListener("input", () => {
    options.onUpdateAddOrderForm(field, input.value);
  });

  wrapper.append(input);
  return wrapper;
}

function createAddOrderSelect(label, field, options, handlers) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const select = document.createElement("select");
  select.name = field;
  select.disabled = state.isSaving;
  options.forEach((option) => {
    select.append(createOption(option.value, option.label, state.addOrderForm[field] === option.value));
  });
  select.addEventListener("change", () => {
    handlers.onUpdateAddOrderForm(field, select.value);
  });

  wrapper.append(select);
  return wrapper;
}

function createOrderEditField(label, field, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = options.wide ? "form-field form-field-wide" : "form-field";
  wrapper.textContent = label;

  const input = document.createElement(options.multiline ? "textarea" : "input");
  input.name = field;
  input.value = state.orderEditForm[field] ?? "";
  input.disabled = state.isSaving;
  if (!options.multiline) {
    input.type = options.type || "text";
  }
  if (options.required) {
    input.required = true;
  }
  if (options.min !== undefined) {
    input.min = options.min;
  }
  input.addEventListener("input", () => {
    options.onUpdateOrderEditForm(field, input.value);
  });

  wrapper.append(input);
  return wrapper;
}

function createOrderEditSelect(label, field, options, handlers) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const select = document.createElement("select");
  select.name = field;
  select.disabled = state.isSaving;
  options.forEach((option) => {
    select.append(createOption(option.value, option.label, state.orderEditForm[field] === option.value));
  });
  select.addEventListener("change", () => {
    handlers.onUpdateOrderEditForm(field, select.value);
  });

  wrapper.append(select);
  return wrapper;
}

function createOrderEditForm(order, handlers) {
  const form = document.createElement("form");
  form.className = "order-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handlers.onSaveOrderEdit(order.order_id);
  });

  const formGrid = document.createElement("div");
  formGrid.className = "form-grid";

  const preferredDriverOptions = [
    { value: "", label: "No preferred driver" },
    ...state.drivers.map((driver) => ({
      value: driver.driver_id,
      label: driver.name,
    })),
  ];

  formGrid.append(
    createOrderEditField("Invoice #", "invoice_number", handlers),
    createOrderEditField("Company Name", "company_name", handlers),
    createOrderEditField("Phone", "phone", { type: "tel", ...handlers }),
    createOrderEditField("Delivery Address", "delivery_address", handlers),
    createOrderEditField("Suburb", "suburb", { required: true, ...handlers }),
    createOrderEditField("Postcode", "postcode", handlers),
    createOrderEditField("Delivery Date", "delivery_date", {
      type: "date",
      required: true,
      ...handlers,
    }),
    createOrderEditField("Zone", "zone", handlers),
    createOrderEditSelect("Urgency", "urgency", [
      { value: "Normal", label: "Normal" },
      { value: "Urgent", label: "Urgent" },
    ], handlers),
    createOrderEditSelect("Preferred Driver", "preferred_driver_id", preferredDriverOptions, handlers),
    createOrderEditField("Pallet Quantity", "pallet_quantity", {
      type: "number",
      min: "0",
      ...handlers,
    }),
    createOrderEditField("Loose Bags Quantity", "loose_bags_quantity", {
      type: "number",
      min: "0",
      ...handlers,
    }),
    createOrderEditField("Start Time", "start_time", { type: "time", ...handlers }),
    createOrderEditField("End Time", "end_time", { type: "time", ...handlers }),
    createOrderEditField("Note", "note", { multiline: true, wide: true, ...handlers }),
  );

  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.orderEditError;
  error.textContent = state.orderEditError;

  const actions = document.createElement("div");
  actions.className = "form-actions";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "button-secondary";
  cancelButton.textContent = "Cancel Edit";
  cancelButton.disabled = state.isSaving;
  cancelButton.addEventListener("click", handlers.onCancelOrderEdit);

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.textContent = state.isSaving ? "Saving..." : "Save Changes";
  saveButton.disabled = state.isSaving;

  actions.append(cancelButton, saveButton);
  form.append(formGrid, error, actions);
  return form;
}
