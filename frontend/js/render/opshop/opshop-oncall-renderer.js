import { formatOptional } from "../../utils/format-utils.js";

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
