import { createRouteGroupContext } from "./opshop-countryside-renderer.js";

import { createPickupCard } from "./opshop-oncall-renderer.js";

import { createRegularPickupDateGroups } from "./opshop-regular-renderer.js";

import {
  changedOpShopAssignments,
  createActionButton,
  createRouteActionLink,
  createMetricGrid,
  createSectionHeading,
  createEmptyState,
  isBusy,
} from "./opshop-renderer-utils.js";

const OPSHOP_TASK_POOL_VIEWS = [
  { view: "regular", label: "Regular" },
  { view: "oncall", label: "Oncall" },
  { view: "countryside", label: "Countryside" },
];

export function createOpShopTaskPool(board, state, actions, onOpenRouteGroupDetail) {
  if (!board) {
    return createEmptyState("No OP SHOP workspace data loaded.", "store");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-opshop-task-pool";
  const toolbar = document.createElement("section");
  toolbar.className = "workspace-context-panel workspace-context-panel-opshop workspace-opshop-task-pool-toolbar";
  const heading = createSectionHeading("OP SHOP Pickup Task Pool");
  const manageTemplates = createRouteActionLink(
    "Manage Templates",
    "#opshop/templates",
  );
  toolbar.append(heading, manageTemplates);

  const tabs = document.createElement("div");
  tabs.className = "workspace-subtabs workspace-subtabs-opshop";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "OP SHOP Task Pool pickup type");
  OPSHOP_TASK_POOL_VIEWS.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "workspace-subtab";
    button.textContent = item.label;
    const isActive = item.view === (state.opshopTaskPoolView || "regular");
    button.classList.toggle("workspace-subtab-active", isActive);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", isActive ? "true" : "false");
    button.addEventListener("click", () => actions.updateOpShopTaskPoolView(item.view));
    tabs.append(button);
  });
  wrapper.append(
    toolbar,
    tabs,
    createPickupList(
      board,
      state.opshopTaskPoolView || "regular",
      state,
      actions,
      onOpenRouteGroupDetail,
    ),
  );
  return wrapper;
}

export function createPickupList(board, route, state, actions, onOpenRouteGroupDetail) {
  if (!board) {
    return createEmptyState("No OP SHOP workspace data loaded.", "store");
  }
  const pickups = pickupListForRoute(board, route);
  const context = getPickupRouteContext(route);
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  wrapper.append(
    createMetricGrid([
      [context.title, pickups.length, context.icon],
      ["Assigned", pickups.filter((pickup) => pickup.is_assigned).length, "user"],
      ["Unassigned", pickups.filter((pickup) => !pickup.is_assigned).length, "store"],
      ["Active route groups", (board.countryside_route_groups || []).length, "route"],
    ]),
    createSectionHeading(context.heading),
  );

  if (route === "regular" || route === "oncall") {
    const taskActions = document.createElement("div");
    taskActions.className = "workspace-action-row workspace-task-operation-toolbar";
    taskActions.append(
      createActionButton(
        "Add Pickup Task",
        () => actions.startAddOpShopPickupTask(route),
        { primary: true },
      ),
    );
    wrapper.append(taskActions);
  }

  if (route === "countryside") {
    wrapper.append(createRouteGroupContext(
      board,
      state,
      actions,
      onOpenRouteGroupDetail,
    ));
  }

  wrapper.append(createAssignmentApplyBar(pickups, state, actions));

  if (route === "regular") {
    wrapper.append(createRegularPickupDateGroups(pickups, state, actions));
  } else {
    const grid = document.createElement("div");
    grid.className = "workspace-card-grid workspace-pickup-grid";
    if (!pickups.length) {
      grid.append(createEmptyState(context.emptyMessage, context.icon));
    } else {
      pickups.forEach((pickup) => grid.append(createPickupCard(pickup, state, actions)));
    }
    wrapper.append(grid);
  }
  return wrapper;
}

export function pickupListForRoute(board, route) {
  return (board.opshop_pickups || []).filter((pickup) => {
    if (route === "regular") {
      return pickup.run_type === "REGULAR";
    }
    if (route === "countryside") {
      return pickup.pickup_category === "COUNTRYSIDE";
    }
    return pickup.run_type === "ON_CALL" && pickup.pickup_category !== "COUNTRYSIDE";
  });
}

export function getPickupRouteContext(route) {
  if (route === "regular") {
    return {
      title: "Regular pickups",
      heading: "Regular Pickup Schedule",
      emptyMessage: "No Regular pickups are visible for this dispatch date.",
      icon: "calendar",
    };
  }
  if (route === "countryside") {
    return {
      title: "Countryside pickups",
      heading: "Countryside Route Pickups",
      emptyMessage: "No Countryside pickups are visible for this dispatch date.",
      icon: "tree",
    };
  }
  return {
    title: "Oncall pickups",
    heading: "Oncall Pickup Requests",
    emptyMessage: "No Oncall pickups are visible for this dispatch date.",
    icon: "phone",
  };
}

export function createAssignmentApplyBar(pickups, state, actions) {
  const bar = document.createElement("section");
  bar.className = "workspace-context-panel workspace-context-panel-opshop workspace-assignment-bar";
  const changedCount = changedOpShopAssignments(pickups, state).length;
  const copy = document.createElement("div");
  const heading = document.createElement("strong");
  heading.textContent = "Assignment changes";
  const detail = document.createElement("span");
  detail.textContent = `${changedCount} pending changes`;
  copy.append(heading, detail);
  const button = createActionButton(
    "Apply Assignment Changes",
    () => actions.applyOpShopAssignmentChanges(pickups),
    {
      disabled: changedCount === 0 || isBusy(state, "opshop-apply-assignments"),
      primary: true,
    },
  );
  bar.append(copy, button);
  return bar;
}
