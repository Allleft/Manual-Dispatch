import { state } from "../state/app-state.js";
import {
  getCountrysideOpShopPickupByTaskId,
  getCountrysideRouteGroupNameById,
  getCountrysideScheduleCandidatesForRouteGroup,
} from "../state/selectors.js";
import { createBadge, createOption } from "../utils/dom-utils.js";
import { formatOptional, truncateText } from "../utils/format-utils.js";

export function renderCountrysideOpShopPickupListModal({
  onCancelForm,
  onCancelRouteGroupForm,
  onCancelRouteTemplateForm,
  onAddRouteTemplate,
  onCloseList,
  onConfirmDelete,
  onCreatePickup,
  onCreateRouteGroup,
  onDisableRouteGroup,
  onMoveRouteTemplate,
  onOpenDetail,
  onRemoveRouteTemplate,
  onRenameRouteGroup,
  onSelectRouteGroup,
  onStartAdd,
  onStartAddRouteTemplate,
  onStartCreatePickupFromRouteTemplate,
  onStartDelete,
  onStartDisableRouteGroup,
  onStartEdit,
  onStartMoveRouteTemplate,
  onStartNewRouteGroup,
  onStartRemoveRouteTemplate,
  onStartRenameRouteGroup,
  onUpdateAssignedDriver,
  onUpdateForm,
  onUpdatePickup,
  onUpdateRouteGroupForm,
  onUpdateRouteTemplateForm,
}) {
  let root = document.querySelector("#opshop-countryside-pickup-list-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "opshop-countryside-pickup-list-root";
    document.body.append(root);
  }

  root.replaceChildren();
  if (!state.isCountrysideOpShopPickupListOpen) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop opshop-pickup-list-backdrop";
  backdrop.addEventListener("click", onCloseList);

  const modal = document.createElement("section");
  modal.className = "order-detail-modal opshop-pickup-list-modal opshop-countryside-pickup-list-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "opshop-countryside-pickup-list-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  modal.append(
    createModalHeader({ onCloseList, onStartAdd }),
    createListSummary(),
    createRouteGroupManagement({
      onSelectRouteGroup,
      onStartDisableRouteGroup,
      onStartNewRouteGroup,
      onStartRenameRouteGroup,
    }),
    createErrorMessage(),
    createRouteGroupForm({
      onCancelRouteGroupForm,
      onCreateRouteGroup,
      onDisableRouteGroup,
      onRenameRouteGroup,
      onUpdateRouteGroupForm,
    }),
    createActiveForm({
      onCancelForm,
      onConfirmDelete,
      onCreatePickup,
      onStartDelete,
      onUpdateForm,
      onUpdatePickup,
    }),
    createRouteTemplateForm({
      onAddRouteTemplate,
      onCancelRouteTemplateForm,
      onMoveRouteTemplate,
      onRemoveRouteTemplate,
      onUpdateRouteTemplateForm,
    }),
    createPickupGroups({ onOpenDetail, onStartEdit, onUpdateAssignedDriver }),
    createRouteTemplatesSection({
      onStartAddRouteTemplate,
      onStartCreatePickupFromRouteTemplate,
      onStartMoveRouteTemplate,
      onStartRemoveRouteTemplate,
    }),
  );

  backdrop.append(modal);
  root.append(backdrop);
}

function createModalHeader({ onCloseList, onStartAdd }) {
  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "OP SHOP PICKUP";

  const title = document.createElement("h2");
  title.id = "opshop-countryside-pickup-list-title";
  title.textContent = "Countryside OP SHOP Pickup List";
  titleWrap.append(kicker, title);

  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.textContent = "Add Pickup Task";
  addButton.disabled = state.isCountrysideOpShopPickupSaving || state.isCountrysideOpShopPickupListLoading;
  addButton.addEventListener("click", (event) => {
    event.stopPropagation();
    onStartAdd();
  });

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  closeButton.textContent = "Close";
  closeButton.addEventListener("click", (event) => {
    event.stopPropagation();
    onCloseList();
  });

  actions.append(addButton, closeButton);
  header.append(titleWrap, actions);
  return header;
}

function createListSummary() {
  const summary = document.createElement("div");
  summary.className = "opshop-list-summary";
  const selectedRouteGroupName = state.selectedCountrysideRouteGroupId
    ? getCountrysideRouteGroupNameById(state.selectedCountrysideRouteGroupId) || "Selected route group"
    : "All route groups";
  summary.append(
    createBadge(`${state.countrysideOpShopPickups.length} Countryside pickups`, "good"),
    createBadge(`${state.countrysideRouteGroups.length} route groups`),
    createBadge(selectedRouteGroupName),
    createBadge("ON_CALL + COUNTRYSIDE"),
  );
  return summary;
}

function createRouteGroupManagement({
  onSelectRouteGroup,
  onStartDisableRouteGroup,
  onStartNewRouteGroup,
  onStartRenameRouteGroup,
}) {
  const wrapper = document.createElement("div");
  wrapper.className = "opshop-route-management-bar";

  const label = document.createElement("label");
  label.className = "form-field opshop-route-group-filter";
  label.textContent = "Route Group";

  const select = document.createElement("select");
  select.disabled = state.isCountrysideOpShopPickupSaving || state.isCountrysideOpShopPickupListLoading;
  select.append(createOption("", "All route groups", !state.selectedCountrysideRouteGroupId));
  state.countrysideRouteGroups.forEach((routeGroup) => {
    select.append(
      createOption(
        routeGroup.route_group_id,
        routeGroup.route_group_name,
        state.selectedCountrysideRouteGroupId === routeGroup.route_group_id,
      ),
    );
  });
  select.addEventListener("change", (event) => {
    event.stopPropagation();
    onSelectRouteGroup(select.value);
  });
  select.addEventListener("click", (event) => event.stopPropagation());

  label.append(select);

  const actions = document.createElement("div");
  actions.className = "opshop-route-management-actions";
  actions.append(
    createSmallActionButton("New Route", onStartNewRouteGroup),
    createSmallActionButton("Rename", onStartRenameRouteGroup, {
      disabled: !state.selectedCountrysideRouteGroupId,
    }),
    createSmallActionButton("Disable", onStartDisableRouteGroup, {
      disabled: !state.selectedCountrysideRouteGroupId,
    }),
  );

  wrapper.append(label, actions);
  return wrapper;
}

function createErrorMessage() {
  const error = document.createElement("p");
  error.className = "board-error";
  const message = state.countrysideOpShopPickupListError || state.countrysideRouteManagementError || "";
  error.hidden = !message;
  error.textContent = message;
  return error;
}

function createRouteGroupForm({
  onCancelRouteGroupForm,
  onCreateRouteGroup,
  onDisableRouteGroup,
  onRenameRouteGroup,
  onUpdateRouteGroupForm,
}) {
  if (!state.countrysideRouteFormMode) {
    return createPlaceholder();
  }

  if (state.countrysideRouteFormMode === "disable") {
    const panel = document.createElement("div");
    panel.className = "opshop-delete-confirmation";

    const message = document.createElement("p");
    message.textContent = `Disable ${formatOptional(state.countrysideRouteForm.route_group_name)}? Existing pickup tasks and saved history will not be deleted.`;

    const actions = document.createElement("div");
    actions.className = "detail-actions";
    actions.append(
      createSubmitLikeButton(
        state.isCountrysideRouteTemplateSaving ? "Disabling..." : "Disable Route",
        onDisableRouteGroup,
        { disabled: state.isCountrysideRouteTemplateSaving },
      ),
      createSecondaryButton("Cancel", onCancelRouteGroupForm),
    );
    panel.append(message, actions);
    return panel;
  }

  const form = document.createElement("form");
  form.className = "opshop-list-form opshop-route-group-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (state.countrysideRouteFormMode === "new") {
      onCreateRouteGroup();
    } else {
      onRenameRouteGroup();
    }
  });

  form.append(
    createTextField(
      "Route Group Name",
      "route_group_name",
      state.countrysideRouteForm.route_group_name,
      onUpdateRouteGroupForm,
      { required: true },
    ),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled: state.isCountrysideRouteTemplateSaving,
      onCancel: onCancelRouteGroupForm,
      submitLabel:
        state.countrysideRouteFormMode === "new"
          ? state.isCountrysideRouteTemplateSaving ? "Saving..." : "Save Route"
          : state.isCountrysideRouteTemplateSaving ? "Saving..." : "Save Route Name",
    }),
  );
  return form;
}

function createActiveForm({
  onCancelForm,
  onConfirmDelete,
  onCreatePickup,
  onStartDelete,
  onUpdateForm,
  onUpdatePickup,
}) {
  if (state.countrysideOpShopPickupFormMode === "add") {
    return createAddForm({ onCancelForm, onCreatePickup, onUpdateForm });
  }
  if (state.countrysideOpShopPickupFormMode === "edit") {
    return createEditForm({ onCancelForm, onStartDelete, onUpdateForm, onUpdatePickup });
  }
  if (state.countrysideOpShopPickupFormMode === "delete") {
    return createDeleteConfirmation({ onCancelForm, onConfirmDelete });
  }

  const spacer = document.createElement("div");
  spacer.className = "opshop-list-form-placeholder";
  return spacer;
}

function createRouteTemplateForm({
  onAddRouteTemplate,
  onCancelRouteTemplateForm,
  onMoveRouteTemplate,
  onRemoveRouteTemplate,
  onUpdateRouteTemplateForm,
}) {
  if (!state.countrysideRouteTemplateFormMode) {
    return createPlaceholder();
  }

  if (state.countrysideRouteTemplateFormMode === "move") {
    return createMoveRouteTemplateForm({
      onCancelRouteTemplateForm,
      onMoveRouteTemplate,
      onUpdateRouteTemplateForm,
    });
  }

  if (state.countrysideRouteTemplateFormMode === "remove") {
    return createRemoveRouteTemplateConfirmation({
      onCancelRouteTemplateForm,
      onRemoveRouteTemplate,
    });
  }

  const form = document.createElement("form");
  form.className = "opshop-list-form opshop-route-template-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onAddRouteTemplate();
  });

  form.append(
    createTextField("OP SHOP Name", "name", state.countrysideRouteTemplateForm.name, onUpdateRouteTemplateForm, {
      required: true,
    }),
    createTextField("Suburb", "suburb", state.countrysideRouteTemplateForm.suburb, onUpdateRouteTemplateForm),
    createTextField(
      "Street Address",
      "street_address",
      state.countrysideRouteTemplateForm.street_address,
      onUpdateRouteTemplateForm,
    ),
    createTextField("Area / Region", "area_region", state.countrysideRouteTemplateForm.area_region, onUpdateRouteTemplateForm),
    createTextField("Primary Contact", "primary_contact", state.countrysideRouteTemplateForm.primary_contact, onUpdateRouteTemplateForm),
    createTextField("Primary Phone", "primary_phone", state.countrysideRouteTemplateForm.primary_phone, onUpdateRouteTemplateForm),
    createTextField(
      "Secondary Contact",
      "secondary_contact",
      state.countrysideRouteTemplateForm.secondary_contact,
      onUpdateRouteTemplateForm,
    ),
    createTextField(
      "Secondary Phone",
      "secondary_phone",
      state.countrysideRouteTemplateForm.secondary_phone,
      onUpdateRouteTemplateForm,
    ),
    createTextField("Time Window", "time_window", state.countrysideRouteTemplateForm.time_window, onUpdateRouteTemplateForm),
    createTextField("Access Type", "access_type", state.countrysideRouteTemplateForm.access_type, onUpdateRouteTemplateForm),
    createCheckboxField(
      "Key Required",
      "key_required",
      state.countrysideRouteTemplateForm.key_required,
      onUpdateRouteTemplateForm,
    ),
    createTextField(
      "Trailer Restriction",
      "trailer_restriction",
      state.countrysideRouteTemplateForm.trailer_restriction,
      onUpdateRouteTemplateForm,
    ),
    createDriverSelect(
      "Default Driver",
      state.countrysideRouteTemplateForm.default_driver_id,
      (value) => onUpdateRouteTemplateForm("default_driver_id", value),
      { disabled: state.isCountrysideRouteTemplateSaving },
    ),
    createTextareaField(
      "Status Notes",
      "status_notes",
      state.countrysideRouteTemplateForm.status_notes,
      onUpdateRouteTemplateForm,
    ),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled: state.isCountrysideRouteTemplateSaving,
      onCancel: onCancelRouteTemplateForm,
      submitLabel: state.isCountrysideRouteTemplateSaving ? "Saving..." : "Save Route Template",
    }),
  );
  return form;
}

function createMoveRouteTemplateForm({
  onCancelRouteTemplateForm,
  onMoveRouteTemplate,
  onUpdateRouteTemplateForm,
}) {
  const form = document.createElement("form");
  form.className = "opshop-list-form opshop-route-template-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onMoveRouteTemplate();
  });

  const heading = document.createElement("p");
  heading.className = "hint-row";
  heading.textContent = `Move ${formatOptional(state.countrysideRouteTemplateForm.name)} to another route group. Existing pickup tasks and saved history stay on their original snapshot.`;

  form.append(
    heading,
    createTargetRouteGroupSelect(onUpdateRouteTemplateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled:
        state.isCountrysideRouteTemplateSaving ||
        !state.countrysideRouteTemplateMoveTargetRouteGroupId,
      onCancel: onCancelRouteTemplateForm,
      submitLabel: state.isCountrysideRouteTemplateSaving ? "Moving..." : "Move",
    }),
  );
  return form;
}

function createRemoveRouteTemplateConfirmation({
  onCancelRouteTemplateForm,
  onRemoveRouteTemplate,
}) {
  const panel = document.createElement("div");
  panel.className = "opshop-delete-confirmation";

  const message = document.createElement("p");
  message.textContent = `Remove ${formatOptional(state.countrysideRouteTemplateForm.name)} from this route? This soft-disables the route template only; the OP SHOP location, pickup tasks, and saved history are not deleted.`;

  const actions = document.createElement("div");
  actions.className = "detail-actions";
  actions.append(
    createSubmitLikeButton(
      state.isCountrysideRouteTemplateSaving ? "Removing..." : "Remove from Route",
      onRemoveRouteTemplate,
      { disabled: state.isCountrysideRouteTemplateSaving },
    ),
    createSecondaryButton("Cancel", onCancelRouteTemplateForm),
  );

  panel.append(message, actions);
  return panel;
}

function createAddForm({ onCancelForm, onCreatePickup, onUpdateForm }) {
  const form = document.createElement("form");
  form.className = "opshop-list-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onCreatePickup();
  });

  form.append(
    createRouteGroupSelect(onUpdateForm),
    createScheduleSelect(onUpdateForm),
    createDateInput("Pickup Date", "pickup_date", state.countrysideOpShopPickupForm.pickup_date, onUpdateForm),
    createDriverSelect(
      "Assigned to",
      state.countrysideOpShopPickupForm.assigned_driver_id,
      (value) => onUpdateForm("assigned_driver_id", value),
      { pickupDate: state.countrysideOpShopPickupForm.pickup_date },
    ),
    createNotesInput(onUpdateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled:
        state.isCountrysideOpShopPickupSaving ||
        !state.countrysideOpShopPickupForm.route_group_id ||
        !state.countrysideOpShopPickupForm.schedule_id ||
        !state.countrysideOpShopPickupForm.pickup_date,
      onCancel: onCancelForm,
      submitLabel: state.isCountrysideOpShopPickupSaving ? "Saving..." : "Save Pickup Task",
    }),
  );

  return form;
}

function createEditForm({ onCancelForm, onStartDelete, onUpdateForm, onUpdatePickup }) {
  const pickup = getCountrysideOpShopPickupByTaskId(state.countrysideOpShopPickupEditingTaskId);
  const isLocked = Boolean(pickup && pickup.assigned_to_locked);
  const canDelete = Boolean(
    pickup && ["ACTIVE", "ASSIGNED"].includes(pickup.status) && !isLocked,
  );
  const form = document.createElement("form");
  form.className = "opshop-list-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onUpdatePickup();
  });

  form.append(
    createDateInput(
      "Pickup Date",
      "pickup_date",
      state.countrysideOpShopPickupForm.pickup_date,
      onUpdateForm,
      { disabled: isLocked || (pickup && pickup.status === "ASSIGNED") },
    ),
    createDriverSelect(
      "Assigned to",
      state.countrysideOpShopPickupForm.assigned_driver_id,
      (value) => onUpdateForm("assigned_driver_id", value),
      { disabled: isLocked, pickupDate: state.countrysideOpShopPickupForm.pickup_date },
    ),
    createNotesInput(onUpdateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled: state.isCountrysideOpShopPickupSaving,
      onCancel: onCancelForm,
      submitLabel: state.isCountrysideOpShopPickupSaving ? "Saving..." : "Save Changes",
    }),
  );

  if (canDelete) {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button-secondary";
    deleteButton.textContent = "Delete Pickup Task";
    deleteButton.disabled = state.isCountrysideOpShopPickupSaving;
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onStartDelete(pickup);
    });
    form.append(deleteButton);
  }

  return form;
}

function createDeleteConfirmation({ onCancelForm, onConfirmDelete }) {
  const pickup = getCountrysideOpShopPickupByTaskId(state.countrysideOpShopPickupEditingTaskId);
  const panel = document.createElement("div");
  panel.className = "opshop-delete-confirmation";

  const message = document.createElement("p");
  message.textContent = `Delete ${formatOptional(pickup && pickup.opshop_name)} on ${formatOptional(
    pickup && pickup.pickup_date,
  )}? This marks the task as CANCELLED and removes any OP SHOP assignment.`;

  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.textContent = state.isCountrysideOpShopPickupSaving ? "Deleting..." : "Delete Pickup Task";
  confirm.disabled = state.isCountrysideOpShopPickupSaving;
  confirm.addEventListener("click", (event) => {
    event.stopPropagation();
    onConfirmDelete();
  });

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button-secondary";
  cancel.textContent = "Cancel";
  cancel.disabled = state.isCountrysideOpShopPickupSaving;
  cancel.addEventListener("click", (event) => {
    event.stopPropagation();
    onCancelForm();
  });

  actions.append(confirm, cancel);
  panel.append(message, actions);
  return panel;
}

function createRouteGroupSelect(onUpdateForm) {
  const label = document.createElement("label");
  label.className = "form-field";
  label.textContent = "Route Group";

  const select = document.createElement("select");
  select.name = "route_group_id";
  select.required = true;
  select.disabled = state.isCountrysideOpShopPickupSaving || state.isCountrysideOpShopPickupListLoading;
  select.append(createOption("", "Select Countryside route group", !state.countrysideOpShopPickupForm.route_group_id));
  state.countrysideRouteGroups.forEach((routeGroup) => {
    select.append(
      createOption(
        routeGroup.route_group_id,
        routeGroup.route_group_name,
        state.countrysideOpShopPickupForm.route_group_id === routeGroup.route_group_id,
      ),
    );
  });
  select.addEventListener("change", () => onUpdateForm("route_group_id", select.value));

  label.append(select);
  return label;
}

function createScheduleSelect(onUpdateForm) {
  const label = document.createElement("label");
  label.className = "form-field form-field-wide";
  label.textContent = "Template";

  const select = document.createElement("select");
  select.name = "schedule_id";
  select.required = true;
  select.disabled =
    state.isCountrysideOpShopPickupSaving ||
    state.isCountrysideOpShopPickupListLoading ||
    !state.countrysideOpShopPickupForm.route_group_id;
  select.append(
    createOption(
      "",
      state.countrysideOpShopPickupForm.route_group_id
        ? "Select Countryside OP SHOP template"
        : "Select a route group first",
      !state.countrysideOpShopPickupForm.schedule_id,
    ),
  );
  getCountrysideScheduleCandidatesForRouteGroup(
    state.countrysideOpShopPickupForm.route_group_id,
  ).forEach((candidate) => {
    const text = [
      candidate.opshop_name,
      candidate.suburb,
      candidate.route_group_name,
      candidate.default_driver_name || candidate.default_driver_alias,
    ]
      .filter(Boolean)
      .join(" - ");
    select.append(
      createOption(
        candidate.schedule_id,
        text,
        state.countrysideOpShopPickupForm.schedule_id === candidate.schedule_id,
      ),
    );
  });
  select.addEventListener("change", () => onUpdateForm("schedule_id", select.value));

  label.append(select);
  return label;
}

function createDateInput(labelText, field, value, onUpdateForm, options = {}) {
  const label = document.createElement("label");
  label.className = "form-field";
  label.textContent = labelText;

  const input = document.createElement("input");
  input.type = "date";
  input.name = field;
  input.value = value || "";
  input.required = true;
  input.disabled = Boolean(options.disabled) || state.isCountrysideOpShopPickupSaving;
  input.addEventListener("input", () => onUpdateForm(field, input.value));

  label.append(input);
  return label;
}

function createDriverSelect(labelText, value, onChange, options = {}) {
  const label = document.createElement("label");
  label.className = "form-field";
  label.textContent = labelText;

  const select = document.createElement("select");
  select.disabled =
    Boolean(options.disabled) ||
    state.isCountrysideOpShopPickupSaving ||
    state.isCountrysideRouteTemplateSaving;
  select.append(createOption("", "Unassigned", !value));
  state.drivers.forEach((driver) => {
    const hasSavedFinalSummary = options.pickupDate
      ? isDriverFinalizedForPickup(driver.driver_id, options.pickupDate)
      : false;
    const option = createOption(
      driver.driver_id,
      hasSavedFinalSummary ? `${driver.name} (Final Summary saved)` : driver.name,
      value === driver.driver_id,
    );
    option.disabled = hasSavedFinalSummary;
    select.append(option);
  });
  select.value = value || "";
  select.addEventListener("change", () => onChange(select.value));

  label.append(select);
  return label;
}

function createTextField(labelText, field, value, onUpdate, options = {}) {
  const label = document.createElement("label");
  label.className = options.wide ? "form-field form-field-wide" : "form-field";
  label.textContent = labelText;

  const input = document.createElement("input");
  input.type = "text";
  input.name = field;
  input.value = value || "";
  input.required = Boolean(options.required);
  input.disabled = state.isCountrysideRouteTemplateSaving;
  input.addEventListener("input", () => onUpdate(field, input.value));

  label.append(input);
  return label;
}

function createTextareaField(labelText, field, value, onUpdate) {
  const label = document.createElement("label");
  label.className = "form-field form-field-wide";
  label.textContent = labelText;

  const textarea = document.createElement("textarea");
  textarea.name = field;
  textarea.rows = 3;
  textarea.value = value || "";
  textarea.disabled = state.isCountrysideRouteTemplateSaving;
  textarea.addEventListener("input", () => onUpdate(field, textarea.value));

  label.append(textarea);
  return label;
}

function createCheckboxField(labelText, field, value, onUpdate) {
  const label = document.createElement("label");
  label.className = "form-field checkbox-field";

  const input = document.createElement("input");
  input.type = "checkbox";
  input.name = field;
  input.checked = Boolean(value);
  input.disabled = state.isCountrysideRouteTemplateSaving;
  input.addEventListener("change", () => onUpdate(field, input.checked));

  const text = document.createElement("span");
  text.textContent = labelText;

  label.append(input, text);
  return label;
}

function createTargetRouteGroupSelect(onUpdateRouteTemplateForm) {
  const label = document.createElement("label");
  label.className = "form-field form-field-wide";
  label.textContent = "Target Route Group";

  const select = document.createElement("select");
  select.required = true;
  select.disabled = state.isCountrysideRouteTemplateSaving;
  select.append(
    createOption(
      "",
      "Select target route group",
      !state.countrysideRouteTemplateMoveTargetRouteGroupId,
    ),
  );
  state.countrysideRouteGroups
    .filter((routeGroup) => routeGroup.route_group_id !== state.countrysideRouteTemplateForm.route_group_id)
    .forEach((routeGroup) => {
      select.append(
        createOption(
          routeGroup.route_group_id,
          routeGroup.route_group_name,
          state.countrysideRouteTemplateMoveTargetRouteGroupId === routeGroup.route_group_id,
        ),
      );
    });
  select.addEventListener("change", () =>
    onUpdateRouteTemplateForm("target_route_group_id", select.value),
  );

  label.append(select);
  return label;
}

function createNotesInput(onUpdateForm) {
  const label = document.createElement("label");
  label.className = "form-field form-field-wide";
  label.textContent = "Notes";

  const textarea = document.createElement("textarea");
  textarea.name = "notes";
  textarea.rows = 3;
  textarea.value = state.countrysideOpShopPickupForm.notes || "";
  textarea.disabled = state.isCountrysideOpShopPickupSaving;
  textarea.addEventListener("input", () => onUpdateForm("notes", textarea.value));

  label.append(textarea);
  return label;
}

function createFormActions({ cancelLabel, isSubmitDisabled, onCancel, submitLabel }) {
  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = submitLabel;
  submit.disabled = isSubmitDisabled;

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button-secondary";
  cancel.textContent = cancelLabel;
  cancel.disabled = state.isCountrysideOpShopPickupSaving;
  cancel.addEventListener("click", (event) => {
    event.stopPropagation();
    onCancel();
  });

  actions.append(submit, cancel);
  return actions;
}

function createSmallActionButton(label, onClick, options = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = options.primary ? "" : "button-secondary";
  button.textContent = label;
  button.disabled =
    Boolean(options.disabled) ||
    state.isCountrysideRouteTemplateSaving ||
    state.isCountrysideOpShopPickupSaving;
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onClick();
  });
  return button;
}

function createSecondaryButton(label, onClick) {
  return createSmallActionButton(label, onClick, { disabled: false });
}

function createSubmitLikeButton(label, onClick, options = {}) {
  return createSmallActionButton(label, onClick, {
    disabled: Boolean(options.disabled),
    primary: true,
  });
}

function createPlaceholder() {
  const placeholder = document.createElement("div");
  placeholder.className = "opshop-list-form-placeholder";
  return placeholder;
}

function createPickupGroups({ onOpenDetail, onStartEdit, onUpdateAssignedDriver }) {
  const container = document.createElement("section");
  container.className = "opshop-list-section opshop-pickup-task-section";

  const heading = document.createElement("h3");
  heading.className = "opshop-list-section-heading";
  heading.textContent = "Pickup Tasks";
  container.append(heading);

  if (state.isCountrysideOpShopPickupListLoading && state.countrysideOpShopPickups.length === 0) {
    const loading = document.createElement("p");
    loading.className = "empty-board";
    loading.textContent = "Loading Countryside OP SHOP pickup list...";
    container.append(loading);
    return container;
  }

  const visiblePickups = getVisibleCountrysidePickups();
  if (visiblePickups.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-board";
    empty.textContent = state.selectedCountrysideRouteGroupId
      ? "No actual Countryside pickup tasks have been created for this route group yet. Use Route Templates below to create one."
      : "No Countryside OP SHOP pickups added.";
    container.append(empty);
    return container;
  }

  const groupList = document.createElement("div");
  groupList.className = "opshop-route-group-list";
  groupPickupsByRouteGroup(visiblePickups).forEach(([routeGroupId, pickups]) => {
    const section = document.createElement("section");
    section.className = "opshop-route-group-section";

    const heading = document.createElement("h3");
    heading.className = "opshop-route-group-heading";
    const title = document.createElement("span");
    title.textContent = getRouteGroupName(routeGroupId);
    const count = document.createElement("span");
    count.className = "opshop-route-group-count";
    count.textContent = `(${pickups.length} ${pickups.length === 1 ? "pickup" : "pickups"})`;
    heading.append(title, count);

    const list = document.createElement("div");
    list.className = "opshop-date-card-list";
    pickups.forEach((pickup) => {
      list.append(createPickupItem(pickup, { onOpenDetail, onStartEdit, onUpdateAssignedDriver }));
    });

    section.append(heading, list);
    groupList.append(section);
  });

  container.append(groupList);
  return container;
}

function createRouteTemplatesSection({
  onStartAddRouteTemplate,
  onStartCreatePickupFromRouteTemplate,
  onStartMoveRouteTemplate,
  onStartRemoveRouteTemplate,
}) {
  const section = document.createElement("section");
  section.className = "opshop-list-section opshop-route-templates-section";

  const header = document.createElement("div");
  header.className = "opshop-list-section-header";

  const title = document.createElement("h3");
  title.className = "opshop-list-section-heading";
  title.textContent = "Route Templates";

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.textContent = "Add OP SHOP to this route";
  addButton.disabled =
    !state.selectedCountrysideRouteGroupId ||
    state.isCountrysideRouteTemplateSaving ||
    state.isCountrysideOpShopPickupListLoading;
  addButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onStartAddRouteTemplate();
  });

  header.append(title, addButton);
  section.append(header);

  if (!state.selectedCountrysideRouteGroupId) {
    const prompt = document.createElement("p");
    prompt.className = "empty-board";
    prompt.textContent = "Select a route group to manage route templates.";
    section.append(prompt);
    return section;
  }

  const routeName = getRouteGroupName(state.selectedCountrysideRouteGroupId);
  const note = document.createElement("p");
  note.className = "hint-row";
  note.textContent = `Managing route templates for ${routeName}. These are ON_CALL + COUNTRYSIDE memberships, not actual pickup tasks.`;
  section.append(note);

  if (state.isCountrysideOpShopPickupListLoading && state.countrysideRouteMemberships.length === 0) {
    const loading = document.createElement("p");
    loading.className = "empty-board";
    loading.textContent = "Loading Countryside route templates...";
    section.append(loading);
    return section;
  }

  if (state.countrysideRouteMemberships.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-board";
    empty.textContent = "No OP SHOP route templates have been added to this route yet.";
    section.append(empty);
    return section;
  }

  const list = document.createElement("div");
  list.className = "opshop-route-template-list";
  state.countrysideRouteMemberships.forEach((template) => {
    list.append(
      createRouteTemplateCard(template, {
        onStartCreatePickupFromRouteTemplate,
        onStartMoveRouteTemplate,
        onStartRemoveRouteTemplate,
      }),
    );
  });
  section.append(list);
  return section;
}

function createRouteTemplateCard(
  template,
  {
    onStartCreatePickupFromRouteTemplate,
    onStartMoveRouteTemplate,
    onStartRemoveRouteTemplate,
  },
) {
  const card = document.createElement("article");
  card.className = "opshop-route-template-card";

  const main = document.createElement("div");
  main.className = "opshop-route-template-main";

  const title = document.createElement("h4");
  title.textContent = formatOptional(template.name);

  const meta = document.createElement("p");
  meta.textContent = [
    template.suburb,
    template.street_address,
    template.primary_phone,
    template.time_window,
    template.default_driver_name || template.default_driver_alias,
  ]
    .filter(Boolean)
    .join(" - ");

  const details = document.createElement("p");
  details.textContent = [
    template.primary_contact ? `Contact: ${template.primary_contact}` : "",
    template.access_type ? `Access: ${template.access_type}` : "",
    template.key_required ? "Key Required" : "",
    template.trailer_restriction ? `Trailer: ${template.trailer_restriction}` : "",
  ]
    .filter(Boolean)
    .join(" - ");

  const notes = document.createElement("p");
  notes.className = "opshop-route-template-notes";
  notes.textContent = truncateText(template.status_notes, 140);
  notes.hidden = !template.status_notes;

  main.append(title, meta, details, notes);

  const actions = document.createElement("div");
  actions.className = "opshop-route-template-actions";
  actions.addEventListener("click", (event) => event.stopPropagation());
  actions.append(
    createSmallActionButton(
      "Create Pickup Task",
      () => onStartCreatePickupFromRouteTemplate(template),
      { primary: true },
    ),
    createSmallActionButton("Move", () => onStartMoveRouteTemplate(template)),
    createSmallActionButton("Remove", () => onStartRemoveRouteTemplate(template)),
  );

  card.append(main, actions);
  return card;
}

function createPickupItem(pickup, { onOpenDetail, onStartEdit, onUpdateAssignedDriver }) {
  const card = document.createElement("article");
  card.className = "opshop-list-item opshop-countryside-list-item";
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `View Countryside OP SHOP PICKUP details for ${pickup.opshop_name || pickup.pickup_task_id}`);
  card.addEventListener("click", () => onOpenDetail(pickup.pickup_task_id));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenDetail(pickup.pickup_task_id);
    }
  });

  const body = document.createElement("div");
  body.className = "opshop-list-item-body";

  const title = document.createElement("h4");
  title.textContent = formatOptional(pickup.opshop_name);

  const meta = document.createElement("div");
  meta.className = "opshop-list-item-meta";

  const suburb = document.createElement("span");
  suburb.className = "opshop-list-item-suburb";
  suburb.textContent = formatOptional(pickup.suburb);

  const routeGroup = document.createElement("span");
  routeGroup.className = "opshop-list-item-date opshop-route-group-name";
  routeGroup.textContent = `Route Group: ${formatOptional(pickup.route_group_name || getRouteGroupName(pickup.route_group_id))}`;

  const pickupDate = document.createElement("span");
  pickupDate.className = "opshop-list-item-date";
  pickupDate.textContent = `Pickup Date: ${formatOptional(pickup.pickup_date)}`;

  meta.append(suburb, routeGroup, pickupDate);
  body.append(title, meta);

  const notePreview = pickup.task_notes || pickup.status_notes;
  if (notePreview) {
    const note = document.createElement("p");
    note.className = "opshop-list-item-note-preview";
    note.textContent = truncateText(notePreview, 96);
    body.append(note);
  }

  const actions = document.createElement("div");
  actions.className = "opshop-list-item-actions";
  actions.addEventListener("click", (event) => event.stopPropagation());
  actions.addEventListener("keydown", (event) => event.stopPropagation());

  actions.append(createAssignedToSelect(pickup, onUpdateAssignedDriver));

  if (!pickup.assigned_to_locked) {
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "button-secondary";
    editButton.textContent = "Edit";
    editButton.disabled = state.isCountrysideOpShopPickupSaving;
    editButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onStartEdit(pickup);
    });
    actions.append(editButton);
  }

  card.append(body, actions);
  return card;
}

function createAssignedToSelect(pickup, onUpdateAssignedDriver) {
  const wrapper = document.createElement("label");
  wrapper.className = "opshop-assigned-to-field";
  wrapper.textContent = "Assigned to";

  const select = document.createElement("select");
  const selectedDriverId =
    state.countrysideOpShopPickupAssignedDriverSelections[pickup.pickup_task_id] ||
    pickup.assigned_driver_id ||
    pickup.driver_id ||
    pickup.default_driver_id ||
    "";
  select.disabled = Boolean(pickup.assigned_to_locked) || state.isCountrysideOpShopPickupSaving;
  select.append(createOption("", "Unassigned", !selectedDriverId));
  state.drivers.forEach((driver) => {
    const hasSavedFinalSummary = isDriverFinalizedForPickup(driver.driver_id, pickup.pickup_date);
    const option = createOption(
      driver.driver_id,
      hasSavedFinalSummary ? `${driver.name} (Final Summary saved)` : driver.name,
      selectedDriverId === driver.driver_id,
    );
    option.disabled = hasSavedFinalSummary;
    select.append(option);
  });
  select.value = selectedDriverId;
  select.addEventListener("change", (event) => {
    event.stopPropagation();
    onUpdateAssignedDriver(pickup.pickup_task_id, select.value);
  });
  select.addEventListener("click", (event) => event.stopPropagation());
  select.addEventListener("keydown", (event) => event.stopPropagation());

  wrapper.append(select);
  if (pickup.assigned_to_locked) {
    const lock = document.createElement("span");
    lock.className = "opshop-assigned-to-lock";
    lock.textContent = "Past pickup date";
    wrapper.append(lock);
  }
  return wrapper;
}

function getVisibleCountrysidePickups() {
  return state.countrysideOpShopPickups.filter(
    (pickup) =>
      !state.selectedCountrysideRouteGroupId ||
      pickup.route_group_id === state.selectedCountrysideRouteGroupId,
  );
}

function groupPickupsByRouteGroup(pickups) {
  const groups = new Map();
  [...pickups]
    .sort(comparePickupsWithinRouteGroup)
    .forEach((pickup) => {
      const key = pickup.route_group_id || "";
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key).push(pickup);
    });
  return [...groups.entries()].sort((left, right) =>
    compareText(getRouteGroupName(left[0]), getRouteGroupName(right[0])),
  );
}

function comparePickupsWithinRouteGroup(left, right) {
  const leftDriverName = getAssignedDriverSortName(left);
  const rightDriverName = getAssignedDriverSortName(right);

  if (leftDriverName && !rightDriverName) {
    return -1;
  }
  if (!leftDriverName && rightDriverName) {
    return 1;
  }

  return (
    compareText(left.pickup_date, right.pickup_date) ||
    compareText(leftDriverName, rightDriverName) ||
    compareText(left.suburb, right.suburb) ||
    compareText(left.opshop_name, right.opshop_name) ||
    compareText(left.pickup_task_id, right.pickup_task_id)
  );
}

function getAssignedDriverSortName(pickup) {
  const selectedDriverId = state.countrysideOpShopPickupAssignedDriverSelections[pickup.pickup_task_id];
  if (selectedDriverId) {
    return getDriverNameById(selectedDriverId) || selectedDriverId;
  }
  if (pickup.assigned_driver_name) {
    return pickup.assigned_driver_name;
  }
  if (pickup.assigned_driver_id || pickup.driver_id) {
    const driverId = pickup.assigned_driver_id || pickup.driver_id;
    return getDriverNameById(driverId) || driverId;
  }
  return pickup.default_driver_name || pickup.default_driver_alias || "";
}

function getDriverNameById(driverId) {
  const driver = state.drivers.find((item) => item.driver_id === driverId);
  return driver ? driver.name : "";
}

function getRouteGroupName(routeGroupId) {
  return getCountrysideRouteGroupNameById(routeGroupId) || "Unassigned Route Group";
}

function isDriverFinalizedForPickup(driverId, pickupDate) {
  return state.finalizedDriverDeliveryDates.some(
    (lockedDate) =>
      lockedDate.driver_id === driverId &&
      lockedDate.delivery_date === pickupDate,
  );
}

function compareText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, {
    sensitivity: "base",
  });
}
