import { createIcon } from "../../utils/icon-utils.js";

import {
  createSelect,
  createDateField,
  createTextField,
  createActionButton,
  createSectionHeading,
  createEmptyState,
  isBusy,
} from "./opshop-renderer-utils.js";

export function createRouteGroupContext(board, state, actions, onOpenRouteGroupDetail) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-opshop";
  section.append(
    createSectionHeading(
      "Route Group Context",
      `${(board.countryside_route_groups || []).length} active countryside route groups`,
    ),
  );
  const list = document.createElement("div");
  list.className = "workspace-route-assignment-list";
  const routeTemplates = templatesByRouteGroup(board);
  (board.countryside_route_groups || []).forEach((group) => {
    list.append(createRouteGroupAssignmentForm(
      group,
      routeTemplates,
      board.opshop_pickups || [],
      state,
      actions,
      onOpenRouteGroupDetail,
    ));
  });
  if (!list.children.length) {
    list.append(createEmptyState("No active Countryside route groups.", "route"));
  }
  section.append(list);
  return section;
}

export function createRouteGroupAssignmentForm(
  group,
  routeTemplates,
  pickups,
  state,
  actions,
  onOpenRouteGroupDetail,
) {
  const row = document.createElement("article");
  row.className = "workspace-record-card workspace-route-group-card";
  const templateCount = (routeTemplates.get(group.route_group_id) || []).length;
  const draft = {
    pickup_date: state.dispatchDate,
    assigned_driver_id: "",
    notes: "",
    ...(state.countrysideRouteGroupDrafts[group.route_group_id] || {}),
  };
  const lockedPickup = pickups.find(
    (pickup) =>
      pickup.route_group_id === group.route_group_id
      && pickup.pickup_date === draft.pickup_date
      && pickup.assigned_to_locked,
  );
  const detailTrigger = document.createElement("button");
  detailTrigger.type = "button";
  detailTrigger.className = "workspace-route-group-detail-trigger";
  detailTrigger.setAttribute(
    "aria-label",
    `View active OP SHOP templates for ${group.route_group_name}`,
  );
  const triggerCopy = document.createElement("span");
  triggerCopy.className = "workspace-route-group-detail-copy";
  const title = document.createElement("strong");
  title.className = "workspace-route-group-detail-title";
  title.textContent = group.route_group_name;
  const meta = document.createElement("span");
  meta.className = "workspace-route-group-detail-count";
  meta.textContent = `${templateCount} active route templates`;
  triggerCopy.append(title, meta);
  const affordance = document.createElement("span");
  affordance.className = "workspace-route-group-detail-affordance";
  affordance.append(createIcon("arrow-right"));
  detailTrigger.append(triggerCopy, affordance);
  detailTrigger.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onOpenRouteGroupDetail({
      group,
      templates: routeTemplates.get(group.route_group_id) || [],
      pickups,
      pickupDate: draft.pickup_date,
      trigger: detailTrigger,
    });
  });
  const controls = document.createElement("div");
  controls.className = "workspace-action-row workspace-action-row-stacked";
  const pickupDateField = createDateField(
    "Pickup date",
    draft.pickup_date,
    (value) => actions.updateCountrysideRouteGroupDraft(
      group.route_group_id,
      "pickup_date",
      value,
    ),
  );
  const driverField = createSelect(
    "Assigned to",
    draft.assigned_driver_id,
    [{ value: "", label: "Select driver" }].concat(
      (state.opshopBoard?.drivers || []).map((driver) => ({
        value: driver.driver_id,
        label: driver.name,
      })),
    ),
    (value) => actions.updateCountrysideRouteGroupDraft(
      group.route_group_id,
      "assigned_driver_id",
      value,
    ),
  );
  const notesField = createTextField(
    "Notes",
    draft.notes,
    (value) => actions.updateCountrysideRouteGroupDraft(
      group.route_group_id,
      "notes",
      value,
    ),
  );
  pickupDateField.querySelector("input").disabled = Boolean(lockedPickup);
  driverField.querySelector("select").disabled = Boolean(lockedPickup);
  notesField.querySelector("input").disabled = Boolean(lockedPickup);
  controls.append(pickupDateField, driverField, notesField);
  const assignButton = createActionButton(
    "Assign Route Group",
    () => actions.assignCountrysideRouteGroup(group.route_group_id),
    {
      disabled:
        templateCount === 0 ||
        Boolean(lockedPickup) ||
        !draft.pickup_date ||
        !draft.assigned_driver_id ||
        isBusy(state, `opshop-route-group:${group.route_group_id}`),
      primary: true,
    },
  );
  if (lockedPickup) {
    const warning = document.createElement("p");
    warning.className = "workspace-status workspace-status-notice";
    warning.textContent = (
      lockedPickup.assignment_lock_reason || "This pickup is locked."
    );
    row.append(detailTrigger, warning, controls, assignButton);
    return row;
  }
  if (templateCount === 0) {
    const warning = document.createElement("p");
    warning.className = "workspace-status workspace-status-notice";
    warning.textContent = "This route group has no active route templates.";
    row.append(detailTrigger, warning, controls, assignButton);
  } else {
    row.append(detailTrigger, controls, assignButton);
  }
  return row;
}

export function templatesByRouteGroup(board) {
  const groups = new Map();
  (board.templates || [])
    .filter((template) =>
      template.pickup_category === "COUNTRYSIDE"
      && template.route_group_id
      && template.active_flag !== false
      && template.status !== "On_Hold",
    )
    .forEach((template) => {
      if (!groups.has(template.route_group_id)) {
        groups.set(template.route_group_id, []);
      }
      groups.get(template.route_group_id).push(template);
    });
  return groups;
}
