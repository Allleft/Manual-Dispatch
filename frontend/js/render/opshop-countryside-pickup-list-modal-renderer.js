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
  onCloseList,
  onConfirmDelete,
  onCreatePickup,
  onOpenDetail,
  onSelectRouteGroup,
  onStartAdd,
  onStartDelete,
  onStartEdit,
  onUpdateAssignedDriver,
  onUpdateForm,
  onUpdatePickup,
}) {
  let root = document.querySelector("#opshop-countryside-pickup-list-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "opshop-countryside-pickup-list-root";
    document.body.append(root);
  }

  root.innerHTML = "";
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
    createRouteGroupFilter(onSelectRouteGroup),
    createErrorMessage(),
    createActiveForm({
      onCancelForm,
      onConfirmDelete,
      onCreatePickup,
      onStartDelete,
      onUpdateForm,
      onUpdatePickup,
    }),
    createPickupGroups({ onOpenDetail, onStartEdit, onUpdateAssignedDriver }),
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

function createRouteGroupFilter(onSelectRouteGroup) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field opshop-route-group-filter";
  wrapper.textContent = "Route Group";

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

  wrapper.append(select);
  return wrapper;
}

function createErrorMessage() {
  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.countrysideOpShopPickupListError;
  error.textContent = state.countrysideOpShopPickupListError || "";
  return error;
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
  select.disabled = Boolean(options.disabled) || state.isCountrysideOpShopPickupSaving;
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

function createPickupGroups({ onOpenDetail, onStartEdit, onUpdateAssignedDriver }) {
  const container = document.createElement("div");
  container.className = "opshop-route-group-list";

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
      ? "No Countryside OP SHOP pickups added for this route group."
      : "No Countryside OP SHOP pickups added.";
    container.append(empty);
    return container;
  }

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
    container.append(section);
  });

  return container;
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
