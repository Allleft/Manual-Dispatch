import { DEFAULT_TRIP_SUMMARY_DATE } from "../../state/app-state.js";


export function createOpShopTripSummaryActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadOpShopRoute = (...args) => context.actions.loadOpShopRoute(...args);
  const runOpShopAction = (...args) => context.actions.runOpShopAction(...args);
  const isOpShopMutationCurrent = (...args) => context.actions.isOpShopMutationCurrent(...args);

  async function loadOpShopTripSummaryData(
    route = state.workspaceRoute,
    pickupDate = state.opshopTripSummaryDate || DEFAULT_TRIP_SUMMARY_DATE,
    requestVersion = ++context.opshopWorkspaceRequestVersion,
    authSessionVersion = state.authSessionVersion,
  ) {
    const scopedPickupDate =
      pickupDate || state.opshopTripSummaryDate || DEFAULT_TRIP_SUMMARY_DATE;
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
    state.opshopTripSummaryDate = nextDate || DEFAULT_TRIP_SUMMARY_DATE;
    if (
      state.workspaceRoute === "opshop/trip-summary"
      || state.workspaceRoute === "opshop/collections"
    ) {
      await loadOpShopRoute(state.workspaceRoute);
      return;
    }
    renderWorkspace();
  }

  async function reorderCountrysidePickups({
    pickupDate,
    driverId,
    orderedPickupTaskIds,
  }) {
    await runOpShopAction(
      `opshop-countryside-order:${pickupDate}:${driverId}`,
      async (mutationContext) => {
        const updatedBoard = await api.reorderOpShopCountrysidePickups({
          pickup_date: pickupDate,
          driver_id: driverId,
          ordered_pickup_task_ids: orderedPickupTaskIds,
        });
        if (
          isOpShopMutationCurrent(mutationContext)
          && state.opshopTripSummaryDate === pickupDate
        ) {
          state.opshopTripSummaryBoard = updatedBoard;
        }
      },
    );
  }

  return {
    loadOpShopTripSummaryData,
    reorderCountrysidePickups,
    updateOpShopTripSummaryDate,
  };
}
