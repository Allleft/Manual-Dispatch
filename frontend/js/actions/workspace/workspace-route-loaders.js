import { DELIVERY_ROUTES, OPSHOP_ROUTES } from "./workspace-request-context.js";

export function createWorkspaceRouteLoaders(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);
  const loadDeliverySavedHistoryData = (...args) => context.actions.loadDeliverySavedHistoryData(...args);
  const loadDeliveryTripSummaryData = (...args) => context.actions.loadDeliveryTripSummaryData(...args);
  const loadOpShopSavedHistoryData = (...args) => context.actions.loadOpShopSavedHistoryData(...args);
  const loadOpShopTripSummaryData = (...args) => context.actions.loadOpShopTripSummaryData(...args);
  const pruneDeliveryDrafts = (...args) => context.actions.pruneDeliveryDrafts(...args);
  const pruneOpShopDrafts = (...args) => context.actions.pruneOpShopDrafts(...args);
  const clearGenerationConfirmationsForRoute = (...args) => context.actions.clearGenerationConfirmationsForRoute(...args);
  const clearDeliveryTaskPoolModals = (...args) => context.actions.clearDeliveryTaskPoolModals(...args);
  const invalidateDeliveryAttachePreview = (...args) => context.actions.invalidateDeliveryAttachePreview(...args);
  const clearDeliveryVehicleTransientState = (...args) => context.actions.clearDeliveryVehicleTransientState(...args);
  const defaultDeliveryAttacheImportState = (...args) => context.actions.defaultDeliveryAttacheImportState(...args);

  async function loadWorkspaceRoute(route = state.workspaceRoute) {
    clearGenerationConfirmationsForRoute(route);
    if (route !== "delivery/trip-summary") {
      clearDeliveryVehicleTransientState();
    }
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
    const authSessionVersion = state.authSessionVersion;
    const requestVersion = ++context.migrationStatusRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.authSessionVersion === authSessionVersion &&
      state.workspaceRoute === route &&
      route === "home" &&
      requestVersion === context.migrationStatusRequestVersion;

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

  async function loadMigrationStatusForHome(message = "") {
    invalidateDeliveryAttachePreview();
    state.workspaceRoute = "home";
    state.activeWorkspace = "";
    state.isDeliveryWorkspaceLoading = false;
    state.isOpShopWorkspaceLoading = false;
    state.deliveryBusyActionKeys = {};
    state.opshopBusyActionKeys = {};
    state.deliveryGenerationConfirmation = null;
    state.opshopGenerationConfirmation = null;
    state.deliveryActionError = "";
    state.opshopActionError = "";
    state.deliveryOrderDetailId = "";
    state.deliveryOrderDetailReadOnly = false;
    state.deliveryOrderForm = {};
    state.deliveryOrderFormMode = "";
    state.deliveryOrderModalError = "";
    state.deliveryAttacheImportState = defaultDeliveryAttacheImportState();
    state.deliverySpecificationModalOpen = false;
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    state.deliverySpecificationError = "";
    state.deliverySpecificationBusyKey = "";
    clearDeliveryVehicleTransientState();
    if (typeof window !== "undefined") {
      if (window.location?.replace) {
        window.location.replace("#home");
      } else if (window.history?.replaceState) {
        window.history.replaceState(null, "", "#home");
        if (typeof window.dispatchEvent === "function" && typeof HashChangeEvent !== "undefined") {
          window.dispatchEvent(new HashChangeEvent("hashchange"));
        }
      }
    }
    state.isWorkspaceMigrationStatusLoading = true;
    state.workspaceMigrationStatusError = message;
    renderWorkspace();
    try {
      state.workspaceMigrationStatus = await api.getWorkspaceMigrationStatus();
    } catch (error) {
      state.workspaceMigrationStatus = null;
      state.workspaceMigrationStatusError =
        message || `Unable to check workspace migration readiness. ${error.message}`;
    } finally {
      state.isWorkspaceMigrationStatusLoading = false;
      renderWorkspace();
    }
  }

  async function loadDeliveryRoute(route) {
    if (route === "delivery/history") {
      await loadDeliverySavedHistoryData(route);
      return;
    }
    const dispatchDate = state.dispatchDate;
    const authSessionVersion = state.authSessionVersion;
    const requestVersion = ++context.deliveryWorkspaceRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.authSessionVersion === authSessionVersion &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      requestVersion === context.deliveryWorkspaceRequestVersion;

    if (route !== "delivery/task-pool") {
      clearDeliveryTaskPoolModals();
    }
    state.isDeliveryWorkspaceLoading = true;
    state.deliveryWorkspaceError = "";
    state.deliveryActionError = "";
    renderWorkspace();
    try {
      if (route === "delivery/task-pool") {
        const board = await api.getDeliveryWorkspaceBoard(dispatchDate);
        if (isCurrent()) {
          state.deliveryBoard = board;
          pruneDeliveryDrafts();
        }
      } else if (route === "delivery/trip-summary") {
        const deliveryDate = state.deliveryTripSummaryDate || dispatchDate;
        await loadDeliveryTripSummaryData(
          route,
          deliveryDate,
          requestVersion,
          authSessionVersion,
        );
        return;
      } else if (route === "delivery/run-sheet") {
        const deliveryDate = state.deliveryTripSummaryDate || dispatchDate;
        const runSheets = await api.listDeliveryRunSheetsByDeliveryDate(
          deliveryDate,
          "",
        );
        if (
          state.isLoggedIn
          && state.authSessionVersion === authSessionVersion
          && state.workspaceRoute === route
          && state.deliveryTripSummaryDate === deliveryDate
          && requestVersion === context.deliveryWorkspaceRequestVersion
        ) {
          state.deliveryRunSheets = runSheets || [];
        }
      }
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
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
    if (route === "opshop/history") {
      await loadOpShopSavedHistoryData(route);
      return;
    }
    const dispatchDate = state.dispatchDate;
    const authSessionVersion = state.authSessionVersion;
    const requestVersion = ++context.opshopWorkspaceRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.authSessionVersion === authSessionVersion &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      requestVersion === context.opshopWorkspaceRequestVersion;

    state.isOpShopWorkspaceLoading = true;
    state.opshopWorkspaceError = "";
    state.opshopActionError = "";
    renderWorkspace();
    try {
      if (route === "opshop/trip-summary") {
        const pickupDate = state.opshopTripSummaryDate || dispatchDate;
        await loadOpShopTripSummaryData(
          route,
          pickupDate,
          requestVersion,
          authSessionVersion,
        );
        return;
      } else if (route === "opshop/collections") {
        const pickupDate = state.opshopTripSummaryDate || dispatchDate;
        const collections = await api.listOpShopPickupCollectionsByPickupDate(
          pickupDate,
          "",
        );
        if (
          state.isLoggedIn
          && state.authSessionVersion === authSessionVersion
          && state.workspaceRoute === route
          && state.opshopTripSummaryDate === pickupDate
          && requestVersion === context.opshopWorkspaceRequestVersion
        ) {
          state.opshopPickupCollections = collections || [];
        }
      } else if (route.startsWith("opshop/task-pool/")) {
        const [board, collections] = await Promise.all([
          api.getOpShopWorkspaceBoard(dispatchDate),
          api.listOpShopPickupCollections(dispatchDate, ""),
        ]);
        if (isCurrent()) {
          state.opshopBoard = board;
          state.opshopPickupCollections = collections || [];
          pruneOpShopDrafts();
        }
      } else {
        const board = await api.getOpShopWorkspaceBoard(dispatchDate);
        if (isCurrent()) {
          state.opshopBoard = board;
          pruneOpShopDrafts();
        }
      }
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
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

  return {
    loadWorkspaceRoute,
    loadMigrationStatus,
    loadMigrationStatusForHome,
    loadDeliveryRoute,
    loadOpShopRoute,
  };
}
