import { state } from "../state/app-state.js";
import { getOpShopPickupByTaskId } from "../state/selectors.js";
import { createBadge, createOption } from "../utils/dom-utils.js";
import { formatOptional } from "../utils/format-utils.js";
import {
  getDateGroupCollapsed,
  getDateGroupListId,
} from "../utils/opshop-date-group-utils.js";

export function renderOncallOpShopPickupListModal({
  onCancelForm,
  onCloseList,
  onConfirmDelete,
  onCreatePickup,
  onOpenDetail,
  onStartAdd,
  onStartDelete,
  onStartEdit,
  onToggleDateGroup,
  onUpdateAssignedDriver,
  onUpdateForm,
  onUpdatePickup,
}) {
  let root = document.querySelector("#opshop-oncall-pickup-list-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "opshop-oncall-pickup-list-root";
    document.body.append(root);
  }

  root.innerHTML = "";
  if (!state.isOncallOpShopPickupListOpen) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop opshop-pickup-list-backdrop";
  backdrop.addEventListener("click", onCloseList);

  const modal = document.createElement("section");
  modal.className = "order-detail-modal opshop-pickup-list-modal opshop-oncall-pickup-list-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "opshop-oncall-pickup-list-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  modal.append(
    createModalHeader({ onCloseList, onStartAdd }),
    createListSummary(),
    createErrorMessage(),
    createActiveForm({
      onCancelForm,
      onConfirmDelete,
      onCreatePickup,
      onStartDelete,
      onUpdateForm,
      onUpdatePickup,
    }),
    createPickupGroups({ onOpenDetail, onStartEdit, onToggleDateGroup, onUpdateAssignedDriver }),
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
  title.id = "opshop-oncall-pickup-list-title";
  title.textContent = "Oncall OP SHOP Pickup List";
  titleWrap.append(kicker, title);

  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.textContent = "Add Pickup Task";
  addButton.disabled = state.isOncallOpShopPickupSaving || state.isOncallOpShopPickupListLoading;
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
  summary.append(
    createBadge(`${state.oncallOpShopPickups.length} Oncall pickups`, "good"),
    createBadge("Created tasks only"),
    createBadge("ACTIVE / ASSIGNED only"),
  );
  return summary;
}

function createErrorMessage() {
  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.oncallOpShopPickupListError;
  error.textContent = state.oncallOpShopPickupListError || "";
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
  if (state.oncallOpShopPickupFormMode === "add") {
    return createAddForm({ onCancelForm, onCreatePickup, onUpdateForm });
  }
  if (state.oncallOpShopPickupFormMode === "edit") {
    return createEditForm({ onCancelForm, onStartDelete, onUpdateForm, onUpdatePickup });
  }
  if (state.oncallOpShopPickupFormMode === "delete") {
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
    createDateInput("Pickup Date", "pickup_date", state.oncallOpShopPickupForm.pickup_date, onUpdateForm),
    createDriverSelect(
      "Assigned to",
      state.oncallOpShopPickupForm.assigned_driver_id,
      (value) => onUpdateForm("assigned_driver_id", value),
    ),
    createNotesInput(onUpdateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled:
        state.isOncallOpShopPickupSaving ||
        !state.oncallOpShopPickupForm.schedule_id ||
        !state.oncallOpShopPickupForm.pickup_date,
      onCancel: onCancelForm,
      submitLabel: state.isOncallOpShopPickupSaving ? "Saving..." : "Save Pickup Task",
    }),
  );

  return form;
}

function createEditForm({ onCancelForm, onStartDelete, onUpdateForm, onUpdatePickup }) {
  const pickup = getOpShopPickupByTaskId(state.oncallOpShopPickupEditingTaskId);
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
      state.oncallOpShopPickupForm.pickup_date,
      onUpdateForm,
      { disabled: isLocked },
    ),
    createDriverSelect(
      "Assigned to",
      state.oncallOpShopPickupForm.assigned_driver_id,
      (value) => onUpdateForm("assigned_driver_id", value),
      { disabled: isLocked },
    ),
    createNotesInput(onUpdateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled: state.isOncallOpShopPickupSaving,
      onCancel: onCancelForm,
      submitLabel: state.isOncallOpShopPickupSaving ? "Saving..." : "Save Changes",
    }),
  );

  if (canDelete) {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button-secondary";
    deleteButton.textContent = "Delete Pickup Task";
    deleteButton.disabled = state.isOncallOpShopPickupSaving;
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onStartDelete(pickup);
    });
    form.append(deleteButton);
  }

  return form;
}

function createDeleteConfirmation({ onCancelForm, onConfirmDelete }) {
  const pickup = getOpShopPickupByTaskId(state.oncallOpShopPickupEditingTaskId);
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
  confirm.textContent = state.isOncallOpShopPickupSaving ? "Deleting..." : "Delete Pickup Task";
  confirm.disabled = state.isOncallOpShopPickupSaving;
  confirm.addEventListener("click", (event) => {
    event.stopPropagation();
    onConfirmDelete();
  });

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button-secondary";
  cancel.textContent = "Cancel";
  cancel.disabled = state.isOncallOpShopPickupSaving;
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
  label.textContent = "Template";

  const select = document.createElement("select");
  select.name = "schedule_id";
  select.required = true;
  select.disabled = state.isOncallOpShopPickupSaving || state.isOncallOpShopPickupListLoading;
  select.append(createOption("", "Select Oncall OP SHOP template", !state.oncallOpShopPickupForm.schedule_id));
  state.oncallOpShopPickupScheduleCandidates.forEach((candidate) => {
    const text = [
      candidate.opshop_name,
      candidate.suburb,
      candidate.run_day || "Gavin",
      candidate.default_driver_name || candidate.default_driver_alias,
    ]
      .filter(Boolean)
      .join(" - ");
    select.append(
      createOption(
        candidate.schedule_id,
        text,
        state.oncallOpShopPickupForm.schedule_id === candidate.schedule_id,
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
  input.disabled = Boolean(options.disabled) || state.isOncallOpShopPickupSaving;
  input.addEventListener("input", () => onUpdateForm(field, input.value));

  label.append(input);
  return label;
}

function createDriverSelect(labelText, value, onChange, options = {}) {
  const label = document.createElement("label");
  label.className = "form-field";
  label.textContent = labelText;

  const select = document.createElement("select");
  select.disabled = Boolean(options.disabled) || state.isOncallOpShopPickupSaving;
  select.append(createOption("", "Unassigned", !value));
  state.drivers.forEach((driver) => {
    select.append(createOption(driver.driver_id, driver.name, value === driver.driver_id));
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
  textarea.value = state.oncallOpShopPickupForm.notes || "";
  textarea.disabled = state.isOncallOpShopPickupSaving;
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
  cancel.disabled = state.isOncallOpShopPickupSaving;
  cancel.addEventListener("click", (event) => {
    event.stopPropagation();
    onCancel();
  });

  actions.append(submit, cancel);
  return actions;
}

function createPickupGroups({ onOpenDetail, onStartEdit, onToggleDateGroup, onUpdateAssignedDriver }) {
  const container = document.createElement("div");
  container.className = "opshop-date-group-list";

  if (state.isOncallOpShopPickupListLoading && state.oncallOpShopPickups.length === 0) {
    const loading = document.createElement("p");
    loading.className = "empty-board";
    loading.textContent = "Loading Oncall OP SHOP pickup list...";
    container.append(loading);
    return container;
  }

  if (state.oncallOpShopPickups.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-board";
    empty.textContent = "No Oncall OP SHOP pickups added.";
    container.append(empty);
    return container;
  }

  groupPickupsByDate(state.oncallOpShopPickups).forEach(([pickupDate, pickups]) => {
    const section = document.createElement("section");
    section.className = "opshop-date-group";
    const collapsed = getDateGroupCollapsed(
      state.collapsedOncallOpShopPickupDates,
      pickupDate,
      state.dispatchDate,
    );
    const listId = getDateGroupListId("oncall", pickupDate);

    const heading = document.createElement("h3");
    heading.className = "opshop-date-group-heading";
    heading.append(createDateGroupToggle({
      collapsed,
      listId,
      onToggleDateGroup,
      pickupCount: pickups.length,
      pickupDate,
    }));
    section.append(heading);

    const list = document.createElement("div");
    list.className = "opshop-date-card-list";
    list.id = listId;
    list.hidden = collapsed;
    pickups.forEach((pickup) => {
      list.append(createPickupItem(pickup, { onOpenDetail, onStartEdit, onUpdateAssignedDriver }));
    });

    section.append(list);
    container.append(section);
  });

  return container;
}

function createDateGroupToggle({
  collapsed,
  listId,
  onToggleDateGroup,
  pickupCount,
  pickupDate,
}) {
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "opshop-date-group-toggle";
  toggle.setAttribute("aria-controls", listId);
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onToggleDateGroup(pickupDate);
  });

  const label = document.createElement("span");
  label.textContent = formatDateHeading(pickupDate);

  const count = document.createElement("span");
  count.className = "opshop-date-group-count";
  count.textContent = `(${pickupCount} ${pickupCount === 1 ? "pickup" : "pickups"})`;

  const stateLabel = document.createElement("span");
  stateLabel.className = "opshop-date-group-state";
  stateLabel.textContent = collapsed ? "Collapsed" : "Expanded";

  const title = document.createElement("span");
  title.append(label, count);
  toggle.append(title, stateLabel);
  return toggle;
}

function createPickupItem(pickup, { onOpenDetail, onStartEdit, onUpdateAssignedDriver }) {
  const card = document.createElement("article");
  card.className = "opshop-list-item";
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `View Oncall OP SHOP PICKUP details for ${pickup.opshop_name || pickup.pickup_task_id}`);
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

  const pickupDate = document.createElement("span");
  pickupDate.className = "opshop-list-item-date";
  pickupDate.textContent = `Pickup Date: ${formatOptional(pickup.pickup_date)}`;

  meta.append(suburb, pickupDate);
  body.append(title, meta);

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
    editButton.disabled = state.isOncallOpShopPickupSaving;
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
    state.oncallOpShopPickupAssignedDriverSelections[pickup.pickup_task_id] ||
    pickup.assigned_driver_id ||
    pickup.driver_id ||
    pickup.default_driver_id ||
    "";
  select.disabled = Boolean(pickup.assigned_to_locked) || state.isOncallOpShopPickupSaving;
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

function isDriverFinalizedForPickup(driverId, pickupDate) {
  return state.finalizedDriverDeliveryDates.some(
    (lockedDate) =>
      lockedDate.driver_id === driverId &&
      lockedDate.delivery_date === pickupDate,
  );
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
  const selectedDriverId = state.oncallOpShopPickupAssignedDriverSelections[pickup.pickup_task_id];
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
    return value || "No pickup date";
  }
  return `${date.toLocaleDateString("en-AU", { weekday: "long" })} ${date.getDate()}/${date.getMonth() + 1}`;
}

function parseLocalDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) {
    return null;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}
