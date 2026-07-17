import { DELIVERY_ROUTES, OPSHOP_ROUTES } from "./workspace-request-context.js";

export function createWorkspaceAsyncGuards(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadMigrationStatusForHome = (...args) => context.actions.loadMigrationStatusForHome(...args);

  async function handleWorkspaceMigrationGuard(error) {
    if (!error || error.status !== 409) {
      return false;
    }
    await loadMigrationStatusForHome(error.message);
    return true;
  }

  function captureMutationContext() {
    return {
      route: state.workspaceRoute,
      dispatchDate: state.dispatchDate,
      deliveryDate: state.deliveryTripSummaryDate,
      pickupDate: state.opshopTripSummaryDate,
      deliveryHistoryDate: state.deliverySavedHistoryDate,
      opshopHistoryDate: state.opshopSavedHistoryDate,
      activeWorkspace: state.activeWorkspace,
    };
  }

  function dispatchMetadataForContext(context) {
    if (
      context.route === "delivery/task-pool"
      || context.route.startsWith("opshop/task-pool/")
    ) {
      return { dispatch_date: context.dispatchDate };
    }
    return {};
  }

  function nextActionToken() {
    context.actionTokenCounter += 1;
    return `action-${context.actionTokenCounter}`;
  }

  function isDeliveryMutationCurrent(context) {
    return (
      state.isLoggedIn &&
      context &&
      state.workspaceRoute === context.route &&
      state.activeWorkspace === context.activeWorkspace &&
      DELIVERY_ROUTES.has(context.route) &&
      (
        context.route === "delivery/task-pool"
          ? state.dispatchDate === context.dispatchDate
          : context.route === "delivery/history"
            ? state.deliverySavedHistoryDate === context.deliveryHistoryDate
            : state.deliveryTripSummaryDate === context.deliveryDate
      )
    );
  }

  function isOpShopMutationCurrent(context) {
    return (
      state.isLoggedIn &&
      context &&
      state.workspaceRoute === context.route &&
      state.activeWorkspace === context.activeWorkspace &&
      OPSHOP_ROUTES.has(context.route) &&
      (
        context.route.startsWith("opshop/task-pool/")
          ? state.dispatchDate === context.dispatchDate
          : context.route === "opshop/history"
            ? state.opshopSavedHistoryDate === context.opshopHistoryDate
            : state.opshopTripSummaryDate === context.pickupDate
      )
    );
  }

  return {
    handleWorkspaceMigrationGuard,
    captureMutationContext,
    dispatchMetadataForContext,
    nextActionToken,
    isDeliveryMutationCurrent,
    isOpShopMutationCurrent,
  };
}
