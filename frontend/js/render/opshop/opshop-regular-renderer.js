import { createIcon } from "../../utils/icon-utils.js";

import { formatOptional } from "../../utils/format-utils.js";

import { createOpShopDateGroupList } from "../opshop-date-group-list-renderer.js";

import {
  compareText,
  compareRegularRouteSequence,
  effectiveRegularRouteDriverName,
  selectedOpShopDriverId,
  currentDriverId,
  defaultDriverHint,
  createSelect,
  createActionButton,
} from "./opshop-renderer-utils.js";

export function createRegularPickupDateGroups(pickups, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-regular-pickup-list";
  section.append(
    createOpShopDateGroupList({
      collapsedDates: state.collapsedRegularOpShopPickupDates || {},
      comparePickups: (left, right) => compareRegularPickups(left, right, state),
      dispatchDate: state.dispatchDate,
      emptyMessage: "No Regular pickups are visible for this dispatch date.",
      idPrefix: "workspace-regular",
      onToggleDateGroup: actions.toggleRegularOpShopDateGroup,
      pickups,
      renderPickup: (pickup) => createRegularPickupRow(pickup, state, actions),
    }),
  );
  return section;
}

export function createRegularPickupRow(pickup, state, actions) {
  const row = document.createElement("article");
  row.className = "opshop-list-item workspace-regular-pickup-row";

  const icon = document.createElement("span");
  icon.className = "opshop-list-item-icon";
  icon.append(createIcon("store"));

  const body = document.createElement("div");
  body.className = "opshop-list-item-body workspace-regular-pickup-main";
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
  const lastPickupDate = document.createElement("span");
  lastPickupDate.className = "opshop-list-item-last-pickup-date";
  lastPickupDate.append(
    createIcon("history"),
    document.createTextNode(
      `Last Pickup Date: ${formatOptional(pickup.last_pickup_date, "No record")}`,
    ),
  );
  meta.append(suburb, pickupDate, lastPickupDate);
  const currentAssignee = document.createElement("p");
  currentAssignee.className = "workspace-regular-current-assignee";
  currentAssignee.textContent = `Current Assignee: ${currentOpShopDriverName(pickup, state)}`;
  body.append(title, meta, currentAssignee);

  const assignment = createRegularPickupAssignment(pickup, state, actions);
  const taskActions = document.createElement("div");
  taskActions.className = "workspace-action-row workspace-regular-pickup-actions";
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
  const controls = document.createElement("div");
  controls.className = "workspace-regular-pickup-controls";
  controls.append(assignment, taskActions);
  row.append(icon, body, controls);
  return row;
}

export function createRegularPickupAssignment(pickup, state, actions) {
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
  field.classList.add("workspace-regular-assignee-field");
  field.querySelector("select").disabled = Boolean(pickup.assigned_to_locked);
  const defaultHint = defaultDriverHint(pickup, state);
  if (defaultHint !== "None") {
    const hint = document.createElement("span");
    hint.className = "workspace-regular-assignment-hint";
    hint.textContent = defaultHint;
    field.append(hint);
  }
  if (pickup.assigned_to_locked) {
    const lock = document.createElement("span");
    lock.className = "workspace-regular-assignment-lock";
    lock.textContent = pickup.assignment_lock_reason || "This pickup is locked.";
    field.append(lock);
  }
  return field;
}

export function currentOpShopDriverName(pickup, state) {
  if (pickup.assigned_driver_name) {
    return pickup.assigned_driver_name;
  }
  const driverId = currentDriverId(pickup);
  const driver = (state.opshopBoard?.drivers || []).find(
    (item) => item.driver_id === driverId,
  );
  return driver?.name || driverId || "Unassigned";
}

export function compareRegularPickups(left, right, state) {
  const leftDriver = effectiveRegularRouteDriverName(left, state);
  const rightDriver = effectiveRegularRouteDriverName(right, state);
  if (leftDriver && !rightDriver) {
    return -1;
  }
  if (!leftDriver && rightDriver) {
    return 1;
  }
  return compareText(leftDriver, rightDriver)
    || compareRegularRouteSequence(left, right);
}

export function selectedOpShopDriverName(pickup, state) {
  const driverId = selectedOpShopDriverId(pickup, state);
  const driver = (state.opshopBoard?.drivers || []).find(
    (item) => item.driver_id === driverId,
  );
  return driver?.name || driverId || "";
}
