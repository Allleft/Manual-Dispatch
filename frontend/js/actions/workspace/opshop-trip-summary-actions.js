export function createOpShopTripSummaryActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadOpShopRoute = (...args) => context.actions.loadOpShopRoute(...args);

  async function loadOpShopTripSummaryData(
    route = state.workspaceRoute,
    pickupDate = state.opshopTripSummaryDate || state.dispatchDate,
    requestVersion = ++context.opshopWorkspaceRequestVersion,
    authSessionVersion = state.authSessionVersion,
  ) {
    const scopedPickupDate =
      pickupDate || state.opshopTripSummaryDate || state.dispatchDate;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.authSessionVersion === authSessionVersion &&
      state.workspaceRoute === route &&
      state.opshopTripSummaryDate === scopedPickupDate &&
      requestVersion === context.opshopWorkspaceRequestVersion;

    const [board, collections] = await Promise.all([
      api.getOpShopTripSummary({
        pickupDate: scopedPickupDate,
      }),
      api.listOpShopPickupCollectionsByPickupDate(
        scopedPickupDate,
        "",
      ),
    ]);
    if (isCurrent()) {
      state.opshopTripSummaryBoard = board;
      state.opshopTripSummaryCollections = collections || [];
    }
  }

  async function updateOpShopTripSummaryDate(nextDate) {
    state.opshopTripSummaryDate = nextDate || state.dispatchDate;
    if (
      state.workspaceRoute === "opshop/trip-summary"
      || state.workspaceRoute === "opshop/collections"
    ) {
      await loadOpShopRoute(state.workspaceRoute);
      return;
    }
    renderWorkspace();
  }

  return {
    loadOpShopTripSummaryData,
    updateOpShopTripSummaryDate,
  };
}
