import { toggleCollapsedPickupDateGroup } from "../../utils/opshop-date-group-utils.js";
import { captureWindowScroll, restoreWindowScroll } from "../../utils/scroll-utils.js";

export function createOpShopWorkspaceActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  function updateOpShopTaskPoolView(view) {
    if (!["regular", "oncall", "countryside"].includes(view)) {
      return;
    }
    const route = `opshop/task-pool/${view}`;
    if (state.workspaceRoute === route) {
      return;
    }
    if (typeof navigateWorkspaceRoute === "function") {
      navigateWorkspaceRoute(route);
      return;
    }
    state.workspaceRoute = route;
    state.opshopTaskPoolView = view;
    renderWorkspace();
  }

  function toggleRegularOpShopDateGroup(pickupDate) {
    const scrollSnapshot = captureWindowScroll();
    state.collapsedRegularOpShopPickupDates = toggleCollapsedPickupDateGroup(
      state.collapsedRegularOpShopPickupDates || {},
      pickupDate,
      state.dispatchDate,
    );
    renderWorkspace();
    restoreWindowScroll(scrollSnapshot);
  }

  function pruneOpShopDrafts() {
    const pickupIds = new Set(
      (state.opshopBoard?.opshop_pickups || []).map((pickup) => pickup.pickup_task_id),
    );
    state.opshopAssignmentDrafts = Object.fromEntries(
      Object.entries(state.opshopAssignmentDrafts || {}).filter(([pickupTaskId]) =>
        pickupIds.has(pickupTaskId),
      ),
    );
    const routeGroupIds = new Set(
      (state.opshopBoard?.countryside_route_groups || []).map(
        (routeGroup) => routeGroup.route_group_id,
      ),
    );
    state.countrysideRouteGroupDrafts = Object.fromEntries(
      Object.entries(state.countrysideRouteGroupDrafts || {}).filter(([routeGroupId]) =>
        routeGroupIds.has(routeGroupId),
      ),
    );
  }

  return {
    updateOpShopTaskPoolView,
    toggleRegularOpShopDateGroup,
    pruneOpShopDrafts,
  };
}
