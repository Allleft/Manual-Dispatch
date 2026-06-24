import {
  apiGetDeliveryWorkspaceBoard,
  apiGetOpShopWorkspaceBoard,
  apiGetWorkspaceMigrationStatus,
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
const DEFAULT_API = {
  getDeliveryWorkspaceBoard: apiGetDeliveryWorkspaceBoard,
  getOpShopWorkspaceBoard: apiGetOpShopWorkspaceBoard,
  getWorkspaceMigrationStatus: apiGetWorkspaceMigrationStatus,
  listDeliveryRunSheets: apiListDeliveryRunSheets,
  listOpShopPickupCollections: apiListOpShopPickupCollections,
};


export function createWorkspaceActions({ state, renderWorkspace, api = DEFAULT_API }) {
  let migrationStatusRequestVersion = 0;
  let deliveryWorkspaceRequestVersion = 0;
  let opshopWorkspaceRequestVersion = 0;

  async function loadWorkspaceRoute(route = state.workspaceRoute) {
    if (!state.isLoggedIn) {
      return;
    }
    if (route === "home") {
      await loadMigrationStatus();
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

  async function loadMigrationStatus() {
    const route = state.workspaceRoute;
    const requestVersion = ++migrationStatusRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      route === "home" &&
      requestVersion === migrationStatusRequestVersion;

    state.isWorkspaceMigrationStatusLoading = true;
    state.workspaceMigrationStatusError = "";
    renderWorkspace();
    try {
      const status = await api.getWorkspaceMigrationStatus();
      if (!isCurrent()) {
        return;
      }
      state.workspaceMigrationStatus = status;
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      state.workspaceMigrationStatus = null;
      state.workspaceMigrationStatusError =
        `Unable to check workspace migration readiness. ${error.message}`;
    } finally {
      if (isCurrent()) {
        state.isWorkspaceMigrationStatusLoading = false;
        renderWorkspace();
      }
    }
  }

  async function loadDeliveryRoute(route) {
    const dispatchDate = state.dispatchDate;
    const requestVersion = ++deliveryWorkspaceRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      requestVersion === deliveryWorkspaceRequestVersion;

    state.isDeliveryWorkspaceLoading = true;
    state.deliveryWorkspaceError = "";
    renderWorkspace();
    try {
      if (route === "delivery/task-pool") {
        const board = await api.getDeliveryWorkspaceBoard(dispatchDate);
        if (isCurrent()) {
          state.deliveryBoard = board;
        }
      } else {
        const status = route === "delivery/history" ? "SAVED" : "";
        const runSheets = await api.listDeliveryRunSheets(dispatchDate, status);
        if (isCurrent()) {
          state.deliveryRunSheets = runSheets || [];
        }
      }
    } catch (error) {
      if (isCurrent()) {
        state.deliveryWorkspaceError =
          `Unable to load Order Delivery workspace. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isDeliveryWorkspaceLoading = false;
        renderWorkspace();
      }
    }
  }

  async function loadOpShopRoute(route) {
    const dispatchDate = state.dispatchDate;
    const requestVersion = ++opshopWorkspaceRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      requestVersion === opshopWorkspaceRequestVersion;

    state.isOpShopWorkspaceLoading = true;
    state.opshopWorkspaceError = "";
    renderWorkspace();
    try {
      if (route === "opshop/collections" || route === "opshop/history") {
        const status = route === "opshop/history" ? "SAVED" : "";
        const collections = await api.listOpShopPickupCollections(
          dispatchDate,
          status,
        );
        if (isCurrent()) {
          state.opshopPickupCollections = collections || [];
        }
      } else {
        const board = await api.getOpShopWorkspaceBoard(dispatchDate);
        if (isCurrent()) {
          state.opshopBoard = board;
        }
      }
    } catch (error) {
      if (isCurrent()) {
        state.opshopWorkspaceError =
          `Unable to load OP SHOP Pickup workspace. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isOpShopWorkspaceLoading = false;
        renderWorkspace();
      }
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
