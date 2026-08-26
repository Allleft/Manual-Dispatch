import { createIcon } from "../../utils/icon-utils.js";

import { formatOptional } from "../../utils/format-utils.js";

import { createOpShopDateGroupList } from "../opshop-date-group-list-renderer.js";

import {
  compareRegularPickups,
  currentOpShopDriverName,
} from "./opshop-regular-renderer.js";

import {
  selectedOpShopDriverId,
  defaultDriverHint,
  createSelect,
  createActionButton,
  appendFact,
  createBadge,
  joinValues,
  isBusy,
} from "./opshop-renderer-utils.js";

export function createOncallPickupDateGroups(pickups, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-regular-pickup-list workspace-oncall-pickup-list";
  section.append(
    createOpShopDateGroupList({
      collapsedDates: state.collapsedOncallOpShopPickupDates || {},
      comparePickups: (left, right) => compareOncallPickups(left, right, state),
      dispatchDate: state.dispatchDate,
      emptyMessage: "No Oncall pickups are visible for this dispatch date.",
      idPrefix: "workspace-oncall",
      onToggleDateGroup: actions.toggleOncallOpShopDateGroup,
      pickups,
      renderPickup: (pickup) => createOncallPickupRow(pickup, state, actions),
    }),
  );
  return section;
}

export function createOncallPickupRow(pickup, state, actions, options = {}) {
  const row = document.createElement("article");
  row.className = "opshop-list-item workspace-regular-pickup-row workspace-oncall-pickup-row";
  if (options.rowClassName) {
    row.classList.add(options.rowClassName);
  }

  const icon = document.createElement("span");
  icon.className = "opshop-list-item-icon";
  icon.append(createIcon("store"));

  const body = document.createElement("div");
  body.className = "opshop-list-item-body workspace-regular-pickup-main workspace-oncall-pickup-main";
  const title = document.createElement("h4");
  title.textContent = formatOptional(pickup.opshop_name);
  const meta = document.createElement("div");
  meta.className = "opshop-list-item-meta";
  const suburb = document.createElement("span");
  suburb.className = "opshop-list-item-suburb";
  suburb.textContent = options.showStreetAddress
    ? [pickup.suburb, pickup.street_address].filter(Boolean).join(" — ")
    : formatOptional(pickup.suburb);
  const pickupDate = document.createElement("span");
  pickupDate.className = "opshop-list-item-date";
  pickupDate.append(
    createIcon("calendar"),
    document.createTextNode(`Pickup Date: ${formatOptional(pickup.pickup_date)}`),
  );
  meta.append(suburb);
  if (options.showPickupDate !== false) {
    meta.append(pickupDate);
  }
  const currentAssignee = document.createElement("p");
  currentAssignee.className = "workspace-regular-current-assignee workspace-oncall-current-assignee";
  currentAssignee.textContent = `Current Assignee: ${currentOpShopDriverName(pickup, state)}`;
  body.append(title, meta, currentAssignee);

  const assignment = createOncallPickupAssignment(pickup, state, actions);
  const taskActions = document.createElement("div");
  taskActions.className = "workspace-action-row workspace-regular-pickup-actions workspace-oncall-pickup-actions";
  taskActions.append(
    createActionButton(
      "View details",
      () => actions.openOpShopPickupDetail(pickup.pickup_task_id),
    ),
    createActionButton(
      "Edit",
      () => actions.startEditOpShopPickupTask(pickup),
      { disabled: Boolean(pickup.assigned_to_locked) },
    ),
    createActionButton(
      "Delete",
      () => actions.startDeleteOpShopPickupTask(pickup),
      { disabled: Boolean(pickup.assigned_to_locked) },
    ),
  );
  if (pickup.is_assigned) {
    taskActions.append(
      createActionButton(
        "Unassign now",
        () => actions.unassignOpShopPickup(pickup.pickup_task_id),
        {
          disabled: pickup.assigned_to_locked
            || isBusy(state, `opshop-unassign:${pickup.pickup_task_id}`),
        },
      ),
    );
  }
  const controls = document.createElement("div");
  controls.className = "workspace-regular-pickup-controls workspace-oncall-pickup-controls";
  controls.append(assignment, taskActions);
  row.append(icon, body, controls);
  return row;
}

export function createOncallPickupAssignment(pickup, state, actions) {
  const selectedDriverId = selectedOpShopDriverId(pickup, state);
  const field = createSelect(
    "Assigned to",
    selectedDriverId,
    [{ value: "", label: "Unassigned" }].concat(
      (state.opshopBoard?.drivers || []).map((driver) => ({
        value: driver.driver_id,
        label: driver.name,
      })),
    ),
    (value) => actions.updateOpShopAssignmentDraft(pickup.pickup_task_id, value),
  );
  field.classList.add("workspace-regular-assignee-field", "workspace-oncall-assignee-field");
  field.querySelector("select").disabled = Boolean(pickup.assigned_to_locked);
  if (pickup.assigned_to_locked) {
    const lock = document.createElement("span");
    lock.className = "workspace-regular-assignment-lock workspace-oncall-assignment-lock";
    lock.textContent = pickup.assignment_lock_reason || "This pickup is locked.";
    field.append(lock);
  }
  return field;
}

export function compareOncallPickups(left, right, state) {
  return compareRegularPickups(left, right, state);
}

export function createPickupCard(pickup, state, actions) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-pickup-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.className = "workspace-record-kicker";
  kicker.textContent = pickup.pickup_category === "COUNTRYSIDE"
    ? formatOptional(pickup.route_group_name, "Countryside")
    : formatOptional(pickup.run_type);
  const title = document.createElement("h3");
  title.textContent = formatOptional(pickup.opshop_name);
  const location = document.createElement("p");
  location.textContent = [pickup.street_address, pickup.suburb].filter(Boolean).join(", ");
  identity.append(kicker, title, location);
  top.append(identity, createBadge(formatOptional(pickup.status, "ACTIVE")));

  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Pickup date", pickup.pickup_date);
  appendFact(facts, "Current assignee", pickup.assigned_driver_name || pickup.driver_id || "Unassigned");
  appendFact(facts, "Suggested default", defaultDriverHint(pickup, state));
  appendFact(facts, "Time window", pickup.time_window);
  appendFact(facts, "Contact", joinValues(pickup.primary_contact, pickup.primary_phone));
  appendFact(facts, "Call before arrival", pickup.call_before_arrival ? formatOptional(pickup.call_timing, "Yes") : "No");
  appendFact(facts, "Access", pickup.access_type);
  appendFact(facts, "Key required", pickup.key_required ? "Yes" : "No");
  appendFact(facts, "Trailer restriction", pickup.trailer_restriction);
  appendFact(facts, "Notes", joinValues(pickup.task_notes, pickup.status_notes));

  const controls = createPickupAssignmentControls(pickup, state, actions);
  const taskActions = document.createElement("div");
  taskActions.className = "workspace-action-row workspace-pickup-task-actions";
  taskActions.append(
    createActionButton(
      "View details",
      () => actions.openOpShopPickupDetail(pickup.pickup_task_id),
    ),
    createActionButton(
      "Edit",
      () => actions.startEditOpShopPickupTask(pickup),
      { disabled: Boolean(pickup.assigned_to_locked) },
    ),
    createActionButton(
      "Delete",
      () => actions.startDeleteOpShopPickupTask(pickup),
      { disabled: Boolean(pickup.assigned_to_locked) },
    ),
  );
  card.append(top, facts, controls, taskActions);
  return card;
}

export function createPickupAssignmentControls(pickup, state, actions) {
  const controls = document.createElement("div");
  controls.className = "workspace-action-row";
  const selectedDriverId = selectedOpShopDriverId(pickup, state);
  const driverSelect = createSelect(
    "Assigned to",
    selectedDriverId,
    [{ value: "", label: "Unassigned" }].concat(
      (state.opshopBoard?.drivers || []).map((driver) => ({
        value: driver.driver_id,
        label: driver.name,
      })),
    ),
    (value) => actions.updateOpShopAssignmentDraft(pickup.pickup_task_id, value),
  );
  driverSelect.querySelector("select").disabled = Boolean(pickup.assigned_to_locked);
  controls.append(driverSelect);
  if (pickup.assigned_to_locked) {
    const lock = document.createElement("span");
    lock.className = "workspace-pickup-assignment-lock";
    lock.textContent = pickup.assignment_lock_reason || "This pickup is locked.";
    controls.append(lock);
  }
  if (pickup.is_assigned) {
    controls.append(
      createActionButton(
        "Unassign now",
        () => actions.unassignOpShopPickup(pickup.pickup_task_id),
        {
          disabled: pickup.assigned_to_locked || isBusy(state, `opshop-unassign:${pickup.pickup_task_id}`),
        },
      ),
    );
  }
  return controls;
}
