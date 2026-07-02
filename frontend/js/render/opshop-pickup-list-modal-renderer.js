import { state } from "../state/app-state.js";
import {
  getOpShopPickupByTaskId,
  isGeneratedTask,
} from "../state/selectors.js";
import {
  createBadge,
  createModalKicker,
  createOption,
  setButtonContent,
} from "../utils/dom-utils.js";
import {
  formatOptional,
} from "../utils/format-utils.js";
import { createIcon } from "../utils/icon-utils.js";
import { getOpShopModalDrivers } from "../utils/opshop-workspace-modal-utils.js";
import { createOpShopDateGroupList } from "./opshop-date-group-list-renderer.js";

export function renderOpShopPickupListModal({
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

  const modal = document.createElement("section");
  modal.className = "order-detail-modal opshop-pickup-list-modal";
  const isScopedFormOnly = Boolean(
    state.activeWorkspace === "opshop" && state.opshopPickupFormMode,
  );
  modal.classList.toggle("opshop-pickup-form-only-modal", isScopedFormOnly);
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "opshop-pickup-list-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  modal.append(createModalHeader({
    isScopedFormOnly,
    onCloseList,
    onStartAdd,
  }));
  if (!isScopedFormOnly) {
    modal.append(createWindowSummary());
  }
  modal.append(
    createErrorMessage(),
    createActiveForm({
      onCancelForm,
      onConfirmDelete,
      onCreatePickup,
      onStartDelete,
      onUpdateForm,
      onUpdatePickup,
    }),
  );
  if (!isScopedFormOnly) {
    modal.append(createPickupGroups({
      onOpenDetail,
      onStartEdit,
      onToggleDateGroup,
      onUpdateAssignedDriver,
    }));
  }

  backdrop.append(modal);
  root.append(backdrop);
}

function createModalHeader({ isScopedFormOnly, onCloseList, onStartAdd }) {
  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = createModalKicker("OP SHOP PICKUP", "bag");

  const title = document.createElement("h2");
  title.id = "opshop-pickup-list-title";
  title.textContent = isScopedFormOnly
    ? scopedFormTitle()
    : "Regular OP SHOP Pickup List";
  titleWrap.append(kicker, title);

  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  setButtonContent(closeButton, "Close", "x", { iconAfter: true });
  closeButton.addEventListener("click", (event) => {
    event.stopPropagation();
    onCloseList();
  });

  if (!isScopedFormOnly) {
    const addButton = document.createElement("button");
    addButton.type = "button";
    setButtonContent(addButton, "Add Pickup Task", "plus");
    addButton.disabled = state.isOpShopPickupSaving || state.isOpShopPickupListLoading;
    addButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onStartAdd();
    });
    actions.append(addButton);
  }
  actions.append(closeButton);
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
    createBadge("ACTIVE unassigned + ASSIGNED"),
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
  onStartDelete,
  onUpdateForm,
  onUpdatePickup,
}) {
  if (state.opshopPickupFormMode === "add") {
    return createAddForm({ onCancelForm, onCreatePickup, onUpdateForm });
  }
  if (state.opshopPickupFormMode === "edit") {
    return createEditForm({ onCancelForm, onStartDelete, onUpdateForm, onUpdatePickup });
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

function createEditForm({ onCancelForm, onStartDelete, onUpdateForm, onUpdatePickup }) {
  const pickup = getOpShopPickupByTaskId(state.opshopPickupEditingTaskId);
  const isAssigned = pickup && pickup.status === "ASSIGNED";
  const lockState = getPickupLockState(
    pickup,
    pickup && (pickup.assigned_driver_id || pickup.driver_id || ""),
  );
  const canDelete = Boolean(
    pickup && ["ACTIVE", "ASSIGNED"].includes(pickup.status) && !lockState.isLocked,
  );
  const form = document.createElement("form");
  form.className = "opshop-list-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onUpdatePickup();
  });

  const note = document.createElement("p");
  note.className = "hint-row";
  note.textContent = lockState.isLocked
    ? lockState.message
    : isAssigned
      ? "Assigned pickups can update notes only. Unassign first to change the pickup date."
      : "Active pickups can update pickup date and notes.";

  form.append(
    note,
    createDateInput(
      "Pickup Date",
      "pickup_date",
      state.opshopPickupForm.pickup_date,
      onUpdateForm,
      { disabled: Boolean(isAssigned) || lockState.isLocked },
    ),
    createNotesInput(onUpdateForm),
    createFormActions({
      cancelLabel: "Cancel",
      isSubmitDisabled: state.isOpShopPickupSaving || lockState.isLocked,
      onCancel: onCancelForm,
      submitLabel: state.isOpShopPickupSaving ? "Saving..." : "Save Changes",
    }),
  );

  if (canDelete) {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button-secondary";
    setButtonContent(deleteButton, "Delete Pickup Task", "trash");
    deleteButton.disabled = state.isOpShopPickupSaving;
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onStartDelete(pickup);
    });
    form.append(deleteButton);
  }

  return form;
}

function createDeleteConfirmation({ onCancelForm, onConfirmDelete }) {
  const pickup = getOpShopPickupByTaskId(state.opshopPickupEditingTaskId);
  const lockState = getPickupLockState(
    pickup,
    pickup && (pickup.assigned_driver_id || pickup.driver_id || ""),
  );
  const panel = document.createElement("div");
  panel.className = "opshop-delete-confirmation";

  const message = document.createElement("p");
  message.textContent = lockState.isLocked
    ? lockState.message
    : `Delete ${formatOptional(pickup && pickup.opshop_name)} on ${formatOptional(
        pickup && pickup.pickup_date,
      )}? This marks the task as CANCELLED and removes any OP SHOP assignment.`;

  const actions = document.createElement("div");
  actions.className = "detail-actions";

  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "button-danger";
  setButtonContent(confirm, state.isOpShopPickupSaving ? "Deleting..." : "Delete Pickup Task", "trash");
  confirm.disabled = state.isOpShopPickupSaving || lockState.isLocked;
  confirm.addEventListener("click", (event) => {
    event.stopPropagation();
    onConfirmDelete();
  });

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button-secondary";
  setButtonContent(cancel, "Cancel", "x", { iconAfter: true });
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
  setButtonContent(submit, submitLabel, "plus");
  submit.disabled = isSubmitDisabled;

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button-secondary";
  setButtonContent(cancel, cancelLabel, "x", { iconAfter: true });
  cancel.disabled = state.isOpShopPickupSaving;
  cancel.addEventListener("click", (event) => {
    event.stopPropagation();
    onCancel();
  });

  actions.append(submit, cancel);
  return actions;
}

function createPickupGroups({ onOpenDetail, onStartEdit, onToggleDateGroup, onUpdateAssignedDriver }) {
  return createOpShopDateGroupList({
    collapsedDates: state.collapsedRegularOpShopPickupDates,
    comparePickups: comparePickupsWithinDateGroup,
    dispatchDate: state.dispatchDate,
    emptyMessage: "No Regular OP SHOP pickups in this week.",
    idPrefix: "regular",
    loading: state.isOpShopPickupListLoading,
    loadingMessage: "Loading OP SHOP pickup list...",
    onToggleDateGroup,
    pickups: state.scheduledOpShopPickups,
    renderPickup: (pickup) => createPickupItem(pickup, {
        onOpenDetail,
        onStartEdit,
        onUpdateAssignedDriver,
      }),
  });
}


function scopedFormTitle() {
  if (state.opshopPickupFormMode === "edit") {
    return "Edit Regular OP SHOP Pickup Task";
  }
  if (state.opshopPickupFormMode === "delete") {
    return "Delete Regular OP SHOP Pickup Task";
  }
  return "Add Regular OP SHOP Pickup Task";
}

function createPickupItem(pickup, {
  onOpenDetail,
  onStartEdit,
  onUpdateAssignedDriver,
}) {
  const lockState = getPickupLockState(
    pickup,
    pickup.assigned_driver_id || pickup.driver_id || "",
  );
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

  const icon = document.createElement("span");
  icon.className = "opshop-list-item-icon";
  icon.append(createIcon("store"));

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
  pickupDate.append(
    createIcon("calendar"),
    document.createTextNode(`Pickup Date: ${formatOptional(pickup.pickup_date)}`),
  );

  meta.append(suburb, pickupDate);
  body.append(title, meta);

  const actions = document.createElement("div");
  actions.className = "opshop-list-item-actions";
  actions.addEventListener("click", (event) => event.stopPropagation());
  actions.addEventListener("keydown", (event) => event.stopPropagation());

  if (state.activeWorkspace !== "opshop") {
    actions.append(createAssignedToSelect(pickup, onUpdateAssignedDriver));
  }

  if (!lockState.isLocked) {
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "button-secondary";
    setButtonContent(editButton, "Edit", "pencil");
    editButton.disabled = state.isOpShopPickupSaving;
    editButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onStartEdit(pickup);
    });
    actions.append(editButton);
  }

  card.append(icon, body, actions);
  return card;
}

function createAssignedToSelect(pickup, onUpdateAssignedDriver) {
  const wrapper = document.createElement("label");
  wrapper.className = "opshop-assigned-to-field";
  wrapper.textContent = "Assigned to";

  const select = document.createElement("select");
  const hasSelection = Object.prototype.hasOwnProperty.call(
    state.opshopPickupAssignedDriverSelections,
    pickup.pickup_task_id,
  );
  const selectedDriverId = hasSelection
    ? state.opshopPickupAssignedDriverSelections[pickup.pickup_task_id]
    : pickup.assigned_driver_id ||
      pickup.driver_id ||
      getDefaultDriverIdForVisiblePickup(pickup) ||
      "";
  const isFinalSummaryLocked = Boolean(
    selectedDriverId && isDriverFinalizedForPickup(selectedDriverId, pickup.pickup_date),
  );
  const isGeneratedFinalSummaryLocked = isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id);
  const isLocked =
    Boolean(pickup.assigned_to_locked) ||
    Boolean(isFinalSummaryLocked) ||
    Boolean(isGeneratedFinalSummaryLocked);
  select.disabled = isLocked || state.isOpShopPickupSaving;
  select.classList.toggle(
    "opshop-assigned-to-select-locked",
    isFinalSummaryLocked || isGeneratedFinalSummaryLocked,
  );
  select.append(createOption("", "Unassigned", !selectedDriverId));
  getOpShopModalDrivers(state).forEach((driver) => {
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
    if (isLocked) {
      return;
    }
    onUpdateAssignedDriver(pickup.pickup_task_id, select.value);
  });
  select.addEventListener("click", (event) => event.stopPropagation());
  select.addEventListener("keydown", (event) => event.stopPropagation());

  wrapper.append(select);
  const defaultHintText = !selectedDriverId ? getDefaultDriverHintText(pickup) : "";
  if (defaultHintText) {
    const hint = document.createElement("span");
    hint.className = "opshop-assigned-to-hint";
    hint.textContent = defaultHintText;
    wrapper.append(hint);
  }
  if (isLocked) {
    const lock = document.createElement("span");
    lock.className = isFinalSummaryLocked || isGeneratedFinalSummaryLocked
      ? "opshop-assigned-to-lock opshop-assigned-to-lock-finalized"
      : "opshop-assigned-to-lock";
    lock.textContent = isFinalSummaryLocked
      ? "Locked - Final Trip Summary saved"
      : isGeneratedFinalSummaryLocked
        ? "Locked - Generated in Final Trip Summary"
        : "Locked - Past pickup date";
    wrapper.append(lock);
  }
  return wrapper;
}

function shouldUseDefaultDriverForVisiblePickup(pickup) {
  return Boolean(
    pickup &&
    pickup.default_driver_id &&
    pickup.pickup_date &&
    state.dispatchDate &&
    pickup.pickup_date >= state.dispatchDate,
  );
}

function defaultDriverExistsForVisiblePickup(pickup) {
  return Boolean(
    pickup &&
      pickup.default_driver_id &&
      getOpShopModalDrivers(state).some(
        (driver) => driver.driver_id === pickup.default_driver_id,
      ),
  );
}

function canUseDefaultDriverForVisiblePickup(pickup) {
  if (!shouldUseDefaultDriverForVisiblePickup(pickup)) {
    return false;
  }
  if (!defaultDriverExistsForVisiblePickup(pickup)) {
    return false;
  }
  if (isDriverFinalizedForPickup(pickup.default_driver_id, pickup.pickup_date)) {
    return false;
  }
  return true;
}

function getDefaultDriverIdForVisiblePickup(pickup) {
  return canUseDefaultDriverForVisiblePickup(pickup) ? pickup.default_driver_id : "";
}

function getDefaultDriverHintText(pickup) {
  const defaultDriverLabel = pickup.default_driver_name || pickup.default_driver_alias || "";
  if (!defaultDriverLabel || canUseDefaultDriverForVisiblePickup(pickup)) {
    return "";
  }

  if (shouldUseDefaultDriverForVisiblePickup(pickup)) {
    if (!defaultDriverExistsForVisiblePickup(pickup)) {
      return `Default: ${defaultDriverLabel} unavailable`;
    }
    if (isDriverFinalizedForPickup(pickup.default_driver_id, pickup.pickup_date)) {
      return `Default: ${defaultDriverLabel} unavailable - Final Summary saved`;
    }
  }

  return `Default: ${defaultDriverLabel}`;
}

function getPickupLockState(pickup, driverIdForFinalSummaryLock = "") {
  const isFinalSummaryLocked = Boolean(
    pickup &&
      driverIdForFinalSummaryLock &&
      isDriverFinalizedForPickup(driverIdForFinalSummaryLock, pickup.pickup_date),
  );
  const isGeneratedFinalSummaryLocked = Boolean(
    pickup && isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id),
  );
  const isPastDateLocked = Boolean(pickup && pickup.assigned_to_locked);
  const isLocked =
    Boolean(isPastDateLocked) ||
    Boolean(isFinalSummaryLocked) ||
    Boolean(isGeneratedFinalSummaryLocked);
  const message = isFinalSummaryLocked
    ? "Locked - Final Trip Summary saved"
    : isGeneratedFinalSummaryLocked
      ? "Locked - Generated in Final Trip Summary"
      : isPastDateLocked
        ? "Locked - Past pickup date"
        : "";
  return {
    isFinalSummaryLocked,
    isGeneratedFinalSummaryLocked,
    isLocked,
    isPastDateLocked,
    message,
  };
}

function isDriverFinalizedForPickup(driverId, pickupDate) {
  return state.finalizedDriverDeliveryDates.some(
    (lockedDate) =>
      lockedDate.driver_id === driverId &&
      lockedDate.delivery_date === pickupDate,
  );
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
  const driver = getOpShopModalDrivers(state).find((item) => item.driver_id === driverId);
  return driver ? driver.name : "";
}

function compareText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, {
    sensitivity: "base",
  });
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
