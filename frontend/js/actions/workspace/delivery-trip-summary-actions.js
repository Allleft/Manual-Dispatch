import { DEFAULT_TRIP_SUMMARY_DATE } from "../../state/app-state.js";


export function createDeliveryTripSummaryActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadDeliveryRoute = (...args) => context.actions.loadDeliveryRoute(...args);
  const pruneDeliveryVehicleDrafts = (...args) => context.actions.pruneDeliveryVehicleDrafts(...args);
  const clearDeliveryVehicleTransientState = (...args) => context.actions.clearDeliveryVehicleTransientState(...args);

  async function loadDeliveryTripSummaryData(
    route = state.workspaceRoute,
    deliveryDate = state.deliveryTripSummaryDate || DEFAULT_TRIP_SUMMARY_DATE,
    requestVersion = ++context.deliveryWorkspaceRequestVersion,
    authSessionVersion = state.authSessionVersion,
  ) {
    const scopedDeliveryDate =
      deliveryDate || state.deliveryTripSummaryDate || DEFAULT_TRIP_SUMMARY_DATE;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.authSessionVersion === authSessionVersion &&
      state.workspaceRoute === route &&
      state.deliveryTripSummaryDate === scopedDeliveryDate &&
      requestVersion === context.deliveryWorkspaceRequestVersion;

    const [board, runSheets] = await Promise.all([
      api.getDeliveryTripSummary({
        deliveryDate: scopedDeliveryDate,
      }),
      api.listDeliveryRunSheetsByDeliveryDate(
        scopedDeliveryDate,
        "",
      ),
    ]);
    if (isCurrent()) {
      state.deliveryTripSummaryBoard = board;
      state.deliveryTripSummaryRunSheets = runSheets || [];
      pruneDeliveryVehicleDrafts(state.deliveryTripSummaryBoard);
    }
  }

  async function updateDeliveryTripSummaryDate(nextDate) {
    const deliveryDate = nextDate || DEFAULT_TRIP_SUMMARY_DATE;
    if (deliveryDate !== state.deliveryTripSummaryDate) {
      clearDeliveryVehicleTransientState();
    }
    state.deliveryTripSummaryDate = deliveryDate;
    if (
      state.workspaceRoute === "delivery/trip-summary"
      || state.workspaceRoute === "delivery/run-sheet"
    ) {
      await loadDeliveryRoute(state.workspaceRoute);
      return;
    }
    renderWorkspace();
  }

  return {
    loadDeliveryTripSummaryData,
    updateDeliveryTripSummaryDate,
  };
}
