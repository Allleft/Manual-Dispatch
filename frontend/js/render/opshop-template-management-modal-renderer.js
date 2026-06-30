import { state } from "../state/app-state.js";
import {
  createBadge,
  createModalKicker,
  createOption,
  setButtonContent,
} from "../utils/dom-utils.js";
import { formatOptional } from "../utils/format-utils.js";


const RUN_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"];


export function renderOpShopTemplateManagementModal({
  onCancelForm,
  onClose,
  onConfirmDisable,
  onSave,
  onSelectTab,
  onStartAdd,
  onStartDisable,
  onStartEdit,
  onToggleIncludeInactive,
  onUpdateForm,
}) {
  let root = document.querySelector("#opshop-template-management-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "opshop-template-management-root";
    document.body.append(root);
  }
  root.innerHTML = "";
  if (!state.isOpShopTemplateManagementOpen) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop opshop-template-backdrop";
  backdrop.addEventListener("click", onClose);

  const modal = document.createElement("section");
  modal.className = "order-detail-modal opshop-template-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "opshop-template-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  modal.append(createHeader(onClose, onStartAdd));
  modal.append(createOpShopTemplateManagementPanel({
    onCancelForm,
    onConfirmDisable,
    onSave,
    onSelectTab,
    onStartAdd,
    onStartDisable,
    onStartEdit,
    onToggleIncludeInactive,
    onUpdateForm,
  }, { showAddButton: false }));
  backdrop.append(modal);
  root.append(backdrop);
}


export function createOpShopTemplateManagementPanel({
  onCancelForm,
  onConfirmDisable,
  onSave,
  onSelectTab,
  onStartAdd,
  onStartDisable,
  onStartEdit,
  onToggleIncludeInactive,
  onUpdateForm,
}, { showAddButton = true } = {}) {
  const panel = document.createElement("section");
  panel.className = "opshop-template-management-panel";
  if (showAddButton) {
    const actions = document.createElement("div");
    actions.className = "detail-actions opshop-template-page-actions";
    actions.append(createAddTemplateButton(onStartAdd));
    panel.append(actions);
  }
  panel.append(
    createTabs(onSelectTab, onToggleIncludeInactive),
    createError(),
    createActiveForm({ onCancelForm, onConfirmDisable, onSave, onUpdateForm }),
    createTemplateList({ onStartDisable, onStartEdit }),
  );
  return panel;
}


function createHeader(onClose, onStartAdd) {
  const header = document.createElement("div");
  header.className = "detail-header";
  const titleWrap = document.createElement("div");
  const kicker = createModalKicker("OP SHOP PICKUP", "bag");
  const title = document.createElement("h2");
  title.id = "opshop-template-title";
  title.textContent = "OP SHOP Template Management";
  titleWrap.append(kicker, title);

  const actions = document.createElement("div");
  actions.className = "detail-actions";
  const add = createAddTemplateButton(onStartAdd);
  const close = document.createElement("button");
  close.type = "button";
  close.className = "button-secondary";
  setButtonContent(close, "Close", "x", { iconAfter: true });
  close.addEventListener("click", onClose);
  actions.append(add, close);
  header.append(titleWrap, actions);
  return header;
}


function createAddTemplateButton(onStartAdd) {
  const add = document.createElement("button");
  add.type = "button";
  setButtonContent(add, "Add Template", "plus");
  add.disabled = state.isOpShopTemplateSaving;
  add.addEventListener("click", onStartAdd);
  return add;
}


function createTabs(onSelectTab, onToggleIncludeInactive) {
  const bar = document.createElement("div");
  bar.className = "opshop-template-toolbar";
  const tabs = document.createElement("div");
  tabs.className = "spec-tabs";
  [["REGULAR", "Regular Templates"], ["ON_CALL", "Oncall Templates"]].forEach(([value, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = state.opshopTemplateActiveTab === value ? "active" : "";
    button.textContent = label;
    button.addEventListener("click", () => onSelectTab(value));
    tabs.append(button);
  });
  const inactive = document.createElement("label");
  inactive.className = "opshop-template-show-inactive";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = state.opshopTemplateIncludeInactive;
  checkbox.addEventListener("change", () => onToggleIncludeInactive(checkbox.checked));
  inactive.append(checkbox, document.createTextNode(" Show disabled templates"));
  bar.append(tabs, inactive);
  return bar;
}


function createError() {
  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.opshopTemplateError;
  error.textContent = state.opshopTemplateError || "";
  return error;
}


function createActiveForm({ onCancelForm, onConfirmDisable, onSave, onUpdateForm }) {
  if (state.opshopTemplateFormMode === "disable") {
    const confirmation = document.createElement("div");
    confirmation.className = "opshop-delete-confirmation";
    const message = document.createElement("p");
    message.textContent = "Disable this template? Existing pickup tasks and saved history will not be deleted.";
    confirmation.append(message, createActions("Disable Template", onConfirmDisable, onCancelForm));
    return confirmation;
  }
  if (!["add", "edit"].includes(state.opshopTemplateFormMode)) {
    return document.createElement("div");
  }
  const form = document.createElement("form");
  form.className = "opshop-template-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    onSave();
  });
  const values = state.opshopTemplateForm;
  form.append(
    selectField("Template Type", "run_type", values.run_type, [["REGULAR", "Regular"], ["ON_CALL", "Oncall"]], onUpdateForm, true),
    selectField(
      "Run Day",
      "run_day",
      values.run_day,
      [["", "No fixed day / Gavin"], ...RUN_DAYS.map((day) => [day, titleCase(day)])],
      onUpdateForm,
      values.run_type === "REGULAR",
    ),
    textField("OP SHOP Name", "name", values.name, onUpdateForm, true),
    textField("Suburb", "suburb", values.suburb, onUpdateForm),
    textField("Street Address", "street_address", values.street_address, onUpdateForm),
    textField("Area / Region", "area_region", values.area_region, onUpdateForm),
    textField("Primary Contact", "primary_contact", values.primary_contact, onUpdateForm),
    textField("Primary Phone", "primary_phone", values.primary_phone, onUpdateForm),
    textField("Secondary Contact", "secondary_contact", values.secondary_contact, onUpdateForm),
    textField("Secondary Phone", "secondary_phone", values.secondary_phone, onUpdateForm),
    textField("Pickup Frequency", "pickup_frequency", values.pickup_frequency, onUpdateForm),
    textField("Time Window", "time_window", values.time_window, onUpdateForm),
    checkboxField("Call Before Arrival", "call_before_arrival", values.call_before_arrival, onUpdateForm),
    textField("Call Timing", "call_timing", values.call_timing, onUpdateForm),
    textField("Access Type", "access_type", values.access_type, onUpdateForm),
    checkboxField("Key Required", "key_required", values.key_required, onUpdateForm),
    textField("Trailer Restriction", "trailer_restriction", values.trailer_restriction, onUpdateForm),
    textField("Status Notes", "status_notes", values.status_notes, onUpdateForm),
    selectField(
      "Default Driver",
      "default_driver_id",
      values.default_driver_id,
      [["", "No default driver"], ...getTemplateDrivers().map((driver) => [driver.driver_id, driver.name])],
      onUpdateForm,
    ),
    createActions(state.opshopTemplateFormMode === "add" ? "Save Template" : "Save Changes", onSave, onCancelForm),
  );
  return form;
}


function getTemplateDrivers() {
  if (state.activeWorkspace === "opshop") {
    return state.opshopBoard?.drivers || [];
  }
  return state.drivers || [];
}


function createTemplateList({ onStartDisable, onStartEdit }) {
  const list = document.createElement("div");
  list.className = "opshop-template-list";
  if (state.isOpShopTemplateLoading) {
    list.textContent = "Loading OP SHOP templates...";
    return list;
  }
  if (state.opshopTemplates.length === 0) {
    list.textContent = "No active templates in this category.";
    return list;
  }
  state.opshopTemplates.forEach((template) => {
    const item = document.createElement("article");
    item.className = "opshop-template-item";
    const body = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = formatOptional(template.name);
    const meta = document.createElement("p");
    meta.textContent = [
      formatOptional(template.suburb, "No suburb"),
      titleCase(template.run_type),
      template.run_day ? titleCase(template.run_day) : "No fixed day",
      formatOptional(template.pickup_frequency, "No frequency"),
      formatOptional(template.time_window, "No time window"),
      formatOptional(template.default_driver_name || template.default_driver_alias, "No default driver"),
    ].join(" | ");
    const status = createBadge(
      template.active_flag ? "Active" : "On Hold / Disabled",
      template.active_flag ? "good" : "",
    );
    body.append(name, meta, status);
    const actions = document.createElement("div");
    actions.className = "detail-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "button-secondary";
    setButtonContent(edit, "Edit", "pencil");
    edit.addEventListener("click", () => onStartEdit(template));
    actions.append(edit);
    if (template.active_flag) {
      const disable = document.createElement("button");
      disable.type = "button";
      disable.className = "button-secondary";
      setButtonContent(disable, "Disable", "trash");
      disable.addEventListener("click", () => onStartDisable(template));
      actions.append(disable);
    }
    item.append(body, actions);
    list.append(item);
  });
  return list;
}


function textField(labelText, field, value, onUpdate, required = false) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const input = document.createElement("input");
  input.type = "text";
  input.value = value || "";
  input.required = required;
  input.disabled = state.isOpShopTemplateSaving;
  input.addEventListener("input", () => onUpdate(field, input.value));
  label.append(input);
  return label;
}


function selectField(labelText, field, value, options, onUpdate, required = false) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const select = document.createElement("select");
  options.forEach(([optionValue, optionLabel]) => {
    select.append(createOption(optionValue, optionLabel));
  });
  select.value = value || "";
  select.required = required;
  select.disabled = state.isOpShopTemplateSaving;
  select.addEventListener("change", () => onUpdate(field, select.value));
  label.append(select);
  return label;
}


function checkboxField(labelText, field, value, onUpdate) {
  const label = document.createElement("label");
  label.className = "opshop-template-checkbox";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(value);
  input.disabled = state.isOpShopTemplateSaving;
  input.addEventListener("change", () => onUpdate(field, input.checked));
  label.append(input, document.createTextNode(labelText));
  return label;
}


function createActions(submitLabel, onSubmit, onCancel) {
  const actions = document.createElement("div");
  actions.className = "detail-actions opshop-template-form-actions";
  const submit = document.createElement("button");
  submit.type = "button";
  setButtonContent(submit, state.isOpShopTemplateSaving ? "Saving..." : submitLabel, "pencil");
  submit.disabled = state.isOpShopTemplateSaving;
  submit.addEventListener("click", onSubmit);
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button-secondary";
  setButtonContent(cancel, "Cancel", "x", { iconAfter: true });
  cancel.disabled = state.isOpShopTemplateSaving;
  cancel.addEventListener("click", onCancel);
  actions.append(submit, cancel);
  return actions;
}


function titleCase(value) {
  return String(value || "")
    .toLowerCase()
    .replace("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
