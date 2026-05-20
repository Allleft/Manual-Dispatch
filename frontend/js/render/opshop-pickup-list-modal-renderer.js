import { state } from "../state/app-state.js";
import { getOpShopPickupByTaskId } from "../state/selectors.js";
import {
  createBadge,
  createOption,
} from "../utils/dom-utils.js";
import {
  formatOptional,
  truncateText,
} from "../utils/format-utils.js";

export function renderOpShopPickupListModal({
  onCancelForm,
  onCloseList,
  onConfirmDelete,
  onCreatePickup,
  onOpenDetail,
  onStartAdd,
  onStartDelete,
  onStartEdit,
  onUpdateAssignedDriver,
  onUpdateForm,
  onUpdatePickup,
}) {
  let root = document.querySelector("#opshop-pickup-list-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "opshop-pickup-list-root";
    document.body.append(root);
  }

  root.innerHTML = "";
  if (!state.isOpShopPickupListOpen) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop opshop-pickup-list-backdrop";
  backdrop.addEventListener("click", onCloseList);

  const modal = document.createElement("section");
  modal.className = "order-detail-modal opshop-pickup-list-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "opshop-pickup-list-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  modal.append(
    createModalHeader({ onCloseList, onStartAdd }),
    createWindowSummary(),
    createErrorMessage(),
    createActiveForm({
      onCancelForm,
      onConfirmDelete,
      onCreatePickup,
      onUpdateForm,
      onUpdatePickup,
    }),
    createPickupGroups({
      onOpenDetail,
      onStartDelete,
      onStartEdit,
      onUpdateAssignedDriver,
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
  title.id = "opshop-pickup-list-title";
  title.textContent = "Regular OP SHOP Pickup List";
  titleWrap.append(kicker, title);

  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.textContent = "Add Pickup Task";
  addButton.disabled = state.isOpShopPickupSaving || state.isOpShopPickupListLoading;
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

function createWindowSummary() {
  const summary = document.createElement("div");
  summary.className = "opshop-list-summary";
  const start = parseLocalDate(state.opshopRegularListWindowStart || state.dispatchDate);
  const end = parseLocalDate(state.opshopRegularListWindowEnd || state.dispatchDate);
  summary.append(
    createBadge(`${state.scheduledOpShopPickups.length} scheduled pickups`, "good"),
    createBadge(`Window: ${formatDateShort(start)} to ${formatDateShort(end)}`),
    createBadge("Monday-Friday week"),
    createBadge("ACTIVE / ASSIGNED only"),
  );
  return summary;
}

function createErrorMessage() {
  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.opshopPickupListError;
  error.textContent = state.opshopPickupListError || "";
  return error;
}

function createActiveForm({
  onCancelForm,
  onConfirmDelete,
  onCreatePickup,
  onUpdateForm,
  onUpdatePickup,
}) {
  if (state.opshopPickupFormMode === "add") {
    return createAddForm({ onCancelForm, onCreatePickup, onUpdateForm });
  }
  if (state.opshopPickupFormMode === "edit") {
    return createEditForm({ onCancelForm, onUpdateForm, onUpdatePickup });
  }
  if (state.opshopPickupFormMode === "delete") {
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
    createScheduleSelect(onUpdateForm),
    createDateInput("Pickup Date", "pickup_date", state.opshopPickupForm.pickup_date, onUpdateForm),
    createNotesInput(onUpdateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled:
        state.isOpShopPickupSaving ||
        !state.opshopPickupForm.schedule_id ||
        !state.opshopPickupForm.pickup_date,
      onCancel: onCancelForm,
      submitLabel: state.isOpShopPickupSaving ? "Saving..." : "Save Pickup Task",
    }),
  );

  return form;
}

function createEditForm({ onCancelForm, onUpdateForm, onUpdatePickup }) {
  const pickup = getOpShopPickupByTaskId(state.opshopPickupEditingTaskId);
  const isAssigned = pickup && pickup.status === "ASSIGNED";
  const form = document.createElement("form");
  form.className = "opshop-list-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onUpdatePickup();
  });

  const note = document.createElement("p");
  note.className = "hint-row";
  note.textContent = isAssigned
    ? "Assigned pickups can update notes only. Unassign first to change the pickup date."
    : "Active pickups can update pickup date and notes.";

  form.append(
    note,
    createDateInput(
      "Pickup Date",
      "pickup_date",
      state.opshopPickupForm.pickup_date,
      onUpdateForm,
      { disabled: Boolean(isAssigned) },
    ),
    createNotesInput(onUpdateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled: state.isOpShopPickupSaving,
      onCancel: onCancelForm,
      submitLabel: state.isOpShopPickupSaving ? "Saving..." : "Save Changes",
    }),
  );

  return form;
}

function createDeleteConfirmation({ onCancelForm, onConfirmDelete }) {
  const pickup = getOpShopPickupByTaskId(state.opshopPickupEditingTaskId);
  const panel = document.createElement("div");
  panel.className = "opshop-delete-confirmation";

  const message = document.createElement("p");
  message.textContent = `Delete ${formatOptional(pickup && pickup.opshop_name)} on ${formatOptional(
    pickup && pickup.pickup_date,
  )}? This marks the task as CANCELLED.`;

  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.textContent = state.isOpShopPickupSaving ? "Deleting..." : "Delete Pickup Task";
  confirm.disabled = state.isOpShopPickupSaving;
  confirm.addEventListener("click", (event) => {
    event.stopPropagation();
    onConfirmDelete();
  });

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button-secondary";
  cancel.textContent = "Cancel";
  cancel.disabled = state.isOpShopPickupSaving;
  cancel.addEventListener("click", (event) => {
    event.stopPropagation();
    onCancelForm();
  });

  actions.append(confirm, cancel);
  panel.append(message, actions);
  return panel;
}

function createScheduleSelect(onUpdateForm) {
  const label = document.createElement("label");
  label.className = "form-field form-field-wide";
  label.textContent = "Schedule";

  const select = document.createElement("select");
  select.name = "schedule_id";
  select.required = true;
  select.disabled = state.isOpShopPickupSaving || state.isOpShopPickupListLoading;
  select.append(createOption("", "Select OP SHOP schedule", !state.opshopPickupForm.schedule_id));
  state.opshopPickupScheduleCandidates.forEach((candidate) => {
    const text = [
      candidate.opshop_name,
      candidate.suburb,
      candidate.run_type,
      candidate.pickup_frequency,
      candidate.run_day,
    ]
      .filter(Boolean)
      .join(" · ");
    select.append(
      createOption(
        candidate.schedule_id,
        text,
        state.opshopPickupForm.schedule_id === candidate.schedule_id,
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
  input.disabled = Boolean(options.disabled) || state.isOpShopPickupSaving;
  input.addEventListener("input", () => onUpdateForm(field, input.value));

  label.append(input);
  return label;
}

function createNotesInput(onUpdateForm) {
  const label = document.createElement("label");
  label.className = "form-field form-field-wide";
  label.textContent = "Notes";

  const textarea = document.createElement("textarea");
  textarea.name = "notes";
  textarea.rows = 3;
  textarea.value = state.opshopPickupForm.notes || "";
  textarea.disabled = state.isOpShopPickupSaving;
  textarea.addEventListener("input", () => onUpdateForm("notes", textarea.value));

  label.append(textarea);
  return label;
}

function createFormActions({
  cancelLabel,
  isSubmitDisabled,
  onCancel,
  submitLabel,
}) {
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
  cancel.disabled = state.isOpShopPickupSaving;
  cancel.addEventListener("click", (event) => {
    event.stopPropagation();
    onCancel();
  });

  actions.append(submit, cancel);
  return actions;
}

function createPickupGroups({ onOpenDetail, onStartDelete, onStartEdit, onUpdateAssignedDriver }) {
  const container = document.createElement("div");
  container.className = "opshop-date-group-list";

  if (state.isOpShopPickupListLoading && state.scheduledOpShopPickups.length === 0) {
    const loading = document.createElement("p");
    loading.className = "empty-board";
    loading.textContent = "Loading OP SHOP pickup list...";
    container.append(loading);
    return container;
  }

  if (state.scheduledOpShopPickups.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-board";
    empty.textContent = "No Regular OP SHOP pickups in this week.";
    container.append(empty);
    return container;
  }

  groupPickupsByDate(state.scheduledOpShopPickups).forEach(([pickupDate, pickups]) => {
    const section = document.createElement("section");
    section.className = "opshop-date-group";

    const heading = document.createElement("h3");
    heading.textContent = formatDateHeading(pickupDate);
    section.append(heading);

    const list = document.createElement("div");
    list.className = "opshop-date-card-list";
    pickups.forEach((pickup) => {
      list.append(createPickupItem(pickup, {
        onOpenDetail,
        onStartDelete,
        onStartEdit,
        onUpdateAssignedDriver,
      }));
    });

    section.append(list);
    container.append(section);
  });

  return container;
}

function createPickupItem(pickup, {
  onOpenDetail,
  onStartDelete,
  onStartEdit,
  onUpdateAssignedDriver,
}) {
  const card = document.createElement("article");
  card.className = "opshop-list-item";
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `View OP SHOP PICKUP details for ${pickup.opshop_name || pickup.pickup_task_id}`);
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
  meta.className = "compact-meta";
  meta.append(
    createBadge(formatOptional(pickup.suburb)),
    createBadge(`Pickup Date: ${formatOptional(pickup.pickup_date)}`),
    createBadge(formatOptional(pickup.run_type, "UNKNOWN"), "good"),
    createBadge(`Frequency: ${formatOptional(pickup.pickup_frequency)}`),
    createBadge(`Status: ${formatOptional(pickup.status)}`),
  );
  if (pickup.time_window) {
    meta.append(createBadge(`Time: ${pickup.time_window}`));
  }
  if (pickup.primary_phone) {
    meta.append(createBadge(`Phone: ${pickup.primary_phone}`));
  }
  if (pickup.is_assigned || pickup.driver_id || pickup.trip_no) {
    meta.append(createBadge(`Assigned: ${formatOptional(pickup.assigned_driver_name || pickup.driver_id)} / ${formatOptional(pickup.trip_no)}`, "warning"));
  } else if (pickup.default_driver_name || pickup.default_driver_alias) {
    meta.append(createBadge(`Default: ${formatOptional(pickup.default_driver_name || pickup.default_driver_alias)}`));
  }

  const note = document.createElement("p");
  note.className = "compact-note opshop-pickup-note";
  note.textContent = `Note: ${truncateText(pickup.status_notes || pickup.task_notes || "None", 72)}`;

  body.append(title, meta, note);

  const actions = document.createElement("div");
  actions.className = "opshop-list-item-actions";
  actions.addEventListener("click", (event) => event.stopPropagation());
  actions.addEventListener("keydown", (event) => event.stopPropagation());

  actions.append(createAssignedToSelect(pickup, onUpdateAssignedDriver));

  const editButton = document.createElement("button");
  editButton.type = "button";
  editButton.className = "button-secondary";
  editButton.textContent = "Edit";
  editButton.disabled = state.isOpShopPickupSaving;
  editButton.addEventListener("click", (event) => {
    event.stopPropagation();
    onStartEdit(pickup);
  });
  actions.append(editButton);

  if (pickup.status === "ACTIVE") {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button-secondary";
    deleteButton.textContent = "Delete";
    deleteButton.disabled = state.isOpShopPickupSaving;
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onStartDelete(pickup);
    });
    actions.append(deleteButton);
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
    state.opshopPickupAssignedDriverSelections[pickup.pickup_task_id] ||
    pickup.assigned_driver_id ||
    pickup.driver_id ||
    pickup.default_driver_id ||
    "";
  select.disabled = Boolean(pickup.assigned_to_locked) || state.isOpShopPickupSaving;
  select.append(createOption("", "Unassigned", !selectedDriverId));
  state.drivers.forEach((driver) => {
    select.append(createOption(driver.driver_id, driver.name, selectedDriverId === driver.driver_id));
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

function groupPickupsByDate(pickups) {
  const groups = new Map();
  [...pickups]
    .sort((left, right) => compareText(left.pickup_date, right.pickup_date))
    .forEach((pickup) => {
      const key = pickup.pickup_date || "";
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key).push(pickup);
    });
  return [...groups.entries()].map(([pickupDate, groupPickups]) => [
    pickupDate,
    [...groupPickups].sort(comparePickupsWithinDateGroup),
  ]);
}

function comparePickupsWithinDateGroup(left, right) {
  const leftDriverName = getAssignedDriverSortName(left);
  const rightDriverName = getAssignedDriverSortName(right);

  if (leftDriverName && !rightDriverName) {
    return -1;
  }
  if (!leftDriverName && rightDriverName) {
    return 1;
  }

  return (
    compareText(leftDriverName, rightDriverName) ||
    compareText(left.suburb, right.suburb) ||
    compareText(left.opshop_name, right.opshop_name) ||
    compareText(left.pickup_task_id, right.pickup_task_id)
  );
}

function getAssignedDriverSortName(pickup) {
  const selectedDriverId = state.opshopPickupAssignedDriverSelections[pickup.pickup_task_id];
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

function compareText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, {
    sensitivity: "base",
  });
}

function formatDateHeading(value) {
  const date = parseLocalDate(value);
  if (!date) {
    return formatOptional(value);
  }
  return `${WEEKDAYS[date.getDay()]} ${date.getDate()}/${date.getMonth() + 1}`;
}

function formatDateShort(date) {
  if (!date) {
    return "-";
  }
  return `${date.getDate()}/${date.getMonth() + 1}`;
}

function parseLocalDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) {
    return null;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];
