import { state } from "../state/app-state.js";
import { getOrderByTaskId } from "../state/selectors.js";
import {
  createDetailField,
  createModalKicker,
  createOption,
  setButtonContent,
} from "../utils/dom-utils.js";
import {
  formatOptional,
  formatProductDetailLine,
  getUrgencyLabel,
} from "../utils/format-utils.js";

export function renderAddOrderPopup({
  onAddProductLine,
  onCloseAddOrder,
  onCreateOrder,
  onRemoveProductLine,
  onUpdateAddOrderForm,
  onUpdateProductLine,
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
  modal.className = "order-detail-modal modal-shell modal-accent-blue";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "add-order-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = createModalKicker("Manual entry", "document");

  const title = document.createElement("h2");
  title.id = "add-order-title";
  title.textContent = "Add New Order";

  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  setButtonContent(closeButton, "Cancel", "x", { iconAfter: true });
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
  setButtonContent(cancelButton, "Cancel", "x", { iconAfter: true });
  cancelButton.disabled = state.isSaving;
  cancelButton.addEventListener("click", onCloseAddOrder);

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  setButtonContent(saveButton, state.isSaving ? "Saving..." : "Save Order", "plus");
  saveButton.disabled = state.isSaving;

  actions.append(cancelButton, saveButton);
  form.append(
    formGrid,
    createProductLineEditor({
      formState: state.addOrderForm,
      onAddProductLine,
      onRemoveProductLine,
      onUpdateProductLine,
    }),
    error,
    actions,
  );
  modal.append(header, form);
  backdrop.append(modal);
  root.append(backdrop);
}

export function renderOrderDetailPopup({
  getOrderEditForm,
  onAddProductLine,
  onCancelOrder,
  onCancelOrderEdit,
  onCloseOrderDetail,
  onRemoveProductLine,
  onSaveOrderEdit,
  onStartOrderEdit,
  onToggleProductDetail,
  onUpdateOrderEditForm,
  onUpdateProductLine,
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
  modal.className = "order-detail-modal modal-shell modal-accent-blue";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "order-detail-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = createModalKicker("ORDER DETAILS", "document");

  const title = document.createElement("h2");
  title.id = "order-detail-title";
  title.textContent = `${formatOptional(order.invoice_number)} - ${formatOptional(order.suburb)}`;

  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  setButtonContent(closeButton, "Close", "x", { iconAfter: true });
  closeButton.addEventListener("click", onCloseOrderDetail);

  const headerActions = document.createElement("div");
  headerActions.className = "detail-actions";

  if (!state.isOrderEditMode) {
    const productDetailButton = document.createElement("button");
    productDetailButton.type = "button";
    productDetailButton.className = "button-secondary";
    setButtonContent(productDetailButton, "Product Detail", "list");
    productDetailButton.addEventListener("click", onToggleProductDetail);

    const editButton = document.createElement("button");
    editButton.type = "button";
    setButtonContent(editButton, "Edit", "pencil");
    editButton.addEventListener("click", () => onStartOrderEdit(order));

    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "button-danger";
    setButtonContent(cancelButton, state.isSaving ? "Cancelling..." : "Cancel Order", "trash");
    cancelButton.disabled = state.isSaving;
    cancelButton.addEventListener("click", () => onCancelOrder(order.order_id));

    headerActions.append(productDetailButton, editButton, cancelButton);
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
        onAddProductLine,
        onCancelOrderEdit,
        onRemoveProductLine,
        onSaveOrderEdit,
        onUpdateOrderEditForm,
        onUpdateProductLine,
      }),
    );
    backdrop.append(modal);
    root.append(backdrop);
    return;
  }

  const details = createOrderReadOnlyLayout({
    ...getOrderEditForm(order),
    urgency: getUrgencyLabel(order),
  });

  const productDetails = createProductDetailPanel(order);

  const detailError = document.createElement("p");
  detailError.className = "board-error";
  detailError.hidden = !state.errorMessage;
  detailError.textContent = state.errorMessage;

  modal.append(header, detailError, details);
  if (state.isProductDetailOpen) {
    modal.append(productDetails);
  }
  backdrop.append(modal);
  root.append(backdrop);
}

function createAddOrderField(label, field, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = options.wide ? "form-field form-field-wide" : "form-field";
  if (isDateOrTimeField(options)) {
    wrapper.classList.add("modal-date-field");
  }
  wrapper.textContent = label;

  const input = document.createElement(options.multiline ? "textarea" : "input");
  input.name = field;
  input.value = state.addOrderForm[field] ?? "";
  input.disabled =
    state.isSaving || isOppositeQuantityFieldDisabled(state.addOrderForm, field);
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
    syncLoadQuantityInputs(input.closest("form"), state.addOrderForm);
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
  if (isDateOrTimeField(options)) {
    wrapper.classList.add("modal-date-field");
  }
  wrapper.textContent = label;

  const input = document.createElement(options.multiline ? "textarea" : "input");
  input.name = field;
  input.value = state.orderEditForm[field] ?? "";
  input.disabled =
    state.isSaving || isOppositeQuantityFieldDisabled(state.orderEditForm, field);
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
    syncLoadQuantityInputs(input.closest("form"), state.orderEditForm);
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

function createOrderReadOnlyField(label, field, formState, options = {}) {
  const fieldCard = createDetailField(label, formState[field]);
  if (options.wide) {
    fieldCard.classList.add("form-field-wide");
  }
  return fieldCard;
}

function createOrderReadOnlySelect(label, field, formState, options) {
  const selected = options.find((option) => option.value === formState[field]);
  return createDetailField(label, selected ? selected.label : formState[field]);
}

function createOrderReadOnlyLayout(formState) {
  const layout = document.createElement("section");
  layout.className = "order-form order-readonly-form";
  layout.append(createOrderFormGrid(formState, { mode: "view" }));
  return layout;
}

function createOrderFormGrid(formState, { mode, handlers = {} }) {
  const formGrid = document.createElement("div");
  formGrid.className = "form-grid";

  const preferredDriverOptions = [
    { value: "", label: "No preferred driver" },
    ...state.drivers.map((driver) => ({
      value: driver.driver_id,
      label: driver.name,
    })),
  ];

  const createField = (label, field, options = {}) =>
    mode === "edit"
      ? createOrderEditField(label, field, { ...options, ...handlers })
      : createOrderReadOnlyField(label, field, formState, options);

  const createSelectField = (label, field, options) =>
    mode === "edit"
      ? createOrderEditSelect(label, field, options, handlers)
      : createOrderReadOnlySelect(label, field, formState, options);

  formGrid.append(
    createField("Invoice #", "invoice_number"),
    createField("Company Name", "company_name"),
    createField("Phone", "phone", { type: "tel" }),
    createField("Delivery Address", "delivery_address"),
    createField("Suburb", "suburb", { required: true }),
    createField("Postcode", "postcode"),
    createField("Delivery Date", "delivery_date", {
      type: "date",
      required: true,
    }),
    createField("Zone", "zone"),
    createSelectField("Urgency", "urgency", [
      { value: "Normal", label: "Normal" },
      { value: "Urgent", label: "Urgent" },
    ]),
    createSelectField("Preferred Driver", "preferred_driver_id", preferredDriverOptions),
    createField("Pallet Quantity", "pallet_quantity", {
      type: "number",
      min: "0",
    }),
    createField("Loose Bags Quantity", "loose_bags_quantity", {
      type: "number",
      min: "0",
    }),
    createField("Start Time", "start_time", { type: "time" }),
    createField("End Time", "end_time", { type: "time" }),
    createField("Note", "note", { multiline: true, wide: true }),
  );

  return formGrid;
}

function createOrderEditForm(order, handlers) {
  const form = document.createElement("form");
  form.className = "order-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handlers.onSaveOrderEdit(order.order_id);
  });

  const formGrid = createOrderFormGrid(state.orderEditForm, {
    handlers,
    mode: "edit",
  });

  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.orderEditError;
  error.textContent = state.orderEditError;

  const actions = document.createElement("div");
  actions.className = "form-actions";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "button-secondary";
  setButtonContent(cancelButton, "Cancel Edit", "x", { iconAfter: true });
  cancelButton.disabled = state.isSaving;
  cancelButton.addEventListener("click", handlers.onCancelOrderEdit);

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  setButtonContent(saveButton, state.isSaving ? "Saving..." : "Save Changes", "pencil");
  saveButton.disabled = state.isSaving;

  actions.append(cancelButton, saveButton);
  form.append(
    formGrid,
    createProductLineEditor({
      formState: state.orderEditForm,
      onAddProductLine: handlers.onAddProductLine,
      onRemoveProductLine: handlers.onRemoveProductLine,
      onUpdateProductLine: handlers.onUpdateProductLine,
    }),
    error,
    actions,
  );
  return form;
}

function createProductDetailPanel(order) {
  const panel = document.createElement("section");
  panel.className = "product-detail-panel";

  const heading = document.createElement("h3");
  heading.textContent = "Product Detail";
  panel.append(heading);

  const productLines = order.product_lines || [];
  if (productLines.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-trip";
    emptyState.textContent = "No product details recorded.";
    panel.append(emptyState);
    return panel;
  }

  const list = document.createElement("div");
  list.className = "product-detail-list";
  productLines.forEach((line, index) => {
    const item = document.createElement("p");
    item.className = "product-detail-row";
    item.textContent = formatProductDetailLine(line, index + 1);
    list.append(item);
  });
  panel.append(list);
  return panel;
}

function createProductLineEditor({
  formState,
  onAddProductLine,
  onRemoveProductLine,
  onUpdateProductLine,
}) {
  const section = document.createElement("section");
  section.className = "product-line-editor";

  const heading = document.createElement("div");
  heading.className = "product-line-heading";

  const title = document.createElement("h3");
  title.textContent = "Product Details";

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "button-secondary";
  setButtonContent(addButton, "Add Product Line", "plus");
  addButton.disabled = state.isSaving;
  addButton.addEventListener("click", onAddProductLine);
  heading.append(title, addButton);

  const helper = document.createElement("p");
  helper.className = "compact-note";
  helper.textContent = "Product lines must use PALLETS or BAGS and match the Order load quantities.";

  section.append(heading, helper);

  const productLines = formState.product_lines || [];
  if (productLines.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-trip";
    emptyState.textContent = "No product details recorded.";
    section.append(emptyState);
    return section;
  }

  const list = document.createElement("div");
  list.className = "product-line-list";
  productLines.forEach((line, index) => {
    const row = document.createElement("div");
    row.className = "product-line-row";

    const productName = createProductLineInput("Product Name", "product_name", line, index, {
      onUpdateProductLine,
      required: true,
    });
    const quantity = createProductLineInput("Quantity", "quantity", line, index, {
      min: "1",
      onUpdateProductLine,
      required: true,
      type: "number",
    });
    const unit = createProductLineUnitSelect(line, index, onUpdateProductLine);

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "button-secondary";
    setButtonContent(removeButton, "Remove", "trash");
    removeButton.disabled = state.isSaving;
    removeButton.addEventListener("click", () => onRemoveProductLine(index));

    row.append(productName, quantity, unit, removeButton);
    list.append(row);
  });
  section.append(list);
  return section;
}

function createProductLineInput(label, field, line, index, options) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const input = document.createElement("input");
  input.name = `product_line_${index}_${field}`;
  input.type = options.type || "text";
  input.value = line[field] ?? "";
  input.disabled = state.isSaving;
  if (options.required) {
    input.required = true;
  }
  if (options.min !== undefined) {
    input.min = options.min;
  }
  input.addEventListener("input", () => {
    options.onUpdateProductLine(index, field, input.value);
  });
  wrapper.append(input);
  return wrapper;
}

function isDateOrTimeField(options = {}) {
  return options.type === "date" || options.type === "time";
}

function createProductLineUnitSelect(line, index, onUpdateProductLine) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = "Unit";

  const select = document.createElement("select");
  select.name = `product_line_${index}_unit`;
  select.disabled = state.isSaving;
  [
    { value: "PALLETS", label: "Pallets" },
    { value: "BAGS", label: "Bags" },
  ].forEach((option) => {
    select.append(createOption(option.value, option.label, line.unit === option.value));
  });
  select.addEventListener("change", () => {
    onUpdateProductLine(index, "unit", select.value);
  });
  wrapper.append(select);
  return wrapper;
}

function isOppositeQuantityFieldDisabled(formState, field) {
  if (field === "pallet_quantity") {
    return Number(formState.loose_bags_quantity || 0) > 0;
  }
  if (field === "loose_bags_quantity") {
    return Number(formState.pallet_quantity || 0) > 0;
  }
  return false;
}

function syncLoadQuantityInputs(form, formState) {
  if (!form) {
    return;
  }

  const palletInput = form.querySelector('[name="pallet_quantity"]');
  const bagInput = form.querySelector('[name="loose_bags_quantity"]');
  if (!palletInput || !bagInput) {
    return;
  }

  palletInput.value = formState.pallet_quantity ?? palletInput.value;
  bagInput.value = formState.loose_bags_quantity ?? bagInput.value;
  palletInput.disabled =
    state.isSaving || isOppositeQuantityFieldDisabled(formState, "pallet_quantity");
  bagInput.disabled =
    state.isSaving || isOppositeQuantityFieldDisabled(formState, "loose_bags_quantity");
}
