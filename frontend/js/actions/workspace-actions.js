import {
  apiGetDeliveryWorkspaceBoard,
  apiGetOpShopWorkspaceBoard,
  apiGetSharedSpecifications,
  apiListDeliveryRunSheets,
  apiListOpShopPickupCollections,
} from "../api/manual-dispatch-api.js";


const DELIVERY_ROUTES = new Set([
  "delivery/task-pool",
  "delivery/run-sheet",
  "delivery/history",
]);
const OPSHOP_ROUTES = new Set([
  "opshop/regular",
  "opshop/oncall",
  "opshop/countryside",
  "opshop/templates",
  "opshop/collections",
  "opshop/history",
]);


export function createWorkspaceActions({ state, renderWorkspace }) {
  async function loadWorkspaceRoute(route = state.workspaceRoute) {
    if (!state.isLoggedIn || route === "home") {
      return;
    }
    if (DELIVERY_ROUTES.has(route)) {
      await loadDeliveryRoute(route);
      return;
    }
    if (OPSHOP_ROUTES.has(route)) {
      await loadOpShopRoute(route);
    }
  }

  async function loadDeliveryRoute(route) {
    state.isDeliveryWorkspaceLoading = true;
    state.deliveryWorkspaceError = "";
    renderWorkspace();
    try {
      if (route === "delivery/task-pool") {
        state.deliveryBoard = await apiGetDeliveryWorkspaceBoard(state.dispatchDate);
      } else {
        const status = route === "delivery/history" ? "SAVED" : "";
        const [runSheets, specifications] = await Promise.all([
          apiListDeliveryRunSheets(state.dispatchDate, status),
          apiGetSharedSpecifications(),
        ]);
        state.deliveryRunSheets = runSheets || [];
        state.sharedSpecifications = specifications || { drivers: [], vehicles: [] };
      }
    } catch (error) {
      state.deliveryWorkspaceError = `Unable to load Order Delivery workspace. ${error.message}`;
    } finally {
      state.isDeliveryWorkspaceLoading = false;
      renderWorkspace();
    }
  }

  async function loadOpShopRoute(route) {
    state.isOpShopWorkspaceLoading = true;
    state.opshopWorkspaceError = "";
    renderWorkspace();
    try {
      if (route === "opshop/collections" || route === "opshop/history") {
        const status = route === "opshop/history" ? "SAVED" : "";
        const [collections, specifications] = await Promise.all([
          apiListOpShopPickupCollections(state.dispatchDate, status),
          apiGetSharedSpecifications(),
        ]);
        state.opshopPickupCollections = collections || [];
        state.sharedSpecifications = specifications || { drivers: [], vehicles: [] };
      } else {
        state.opshopBoard = await apiGetOpShopWorkspaceBoard(state.dispatchDate);
      }
    } catch (error) {
      state.opshopWorkspaceError = `Unable to load OP SHOP Pickup workspace. ${error.message}`;
    } finally {
      state.isOpShopWorkspaceLoading = false;
      renderWorkspace();
    }
  }

  async function updateDispatchDate(nextDate) {
    if (!nextDate || nextDate === state.dispatchDate) {
      return;
    }
    state.dispatchDate = nextDate;
    await loadWorkspaceRoute(state.workspaceRoute);
  }

  return {
    loadWorkspaceRoute,
    updateDispatchDate,
  };
}
