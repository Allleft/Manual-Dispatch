export function createDeliveryHistoryActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);

  async function loadDeliverySavedHistoryData(
    route = state.workspaceRoute,
    historyDate = state.deliverySavedHistoryDate,
    requestVersion = ++context.deliveryWorkspaceRequestVersion,
  ) {
    const authSessionVersion = state.authSessionVersion;
    const requestedHistoryDate =
      historyDate || state.deliverySavedHistoryDate || state.dispatchDate;
    state.deliverySavedHistoryDate = requestedHistoryDate;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.authSessionVersion === authSessionVersion &&
      state.workspaceRoute === "delivery/history" &&
      route === "delivery/history" &&
      state.deliverySavedHistoryDate === requestedHistoryDate &&
      requestVersion === context.deliveryWorkspaceRequestVersion;

    state.deliverySavedHistoryRunSheets = [];
    state.isDeliveryWorkspaceLoading = true;
    state.deliveryWorkspaceError = "";
    state.deliveryActionError = "";
    renderWorkspace();
    try {
      const runSheets = await api.listDeliveryRunSheetsByDeliveryDate(
        requestedHistoryDate,
        "SAVED",
      );
      if (isCurrent()) {
        state.deliverySavedHistoryRunSheets = sortDeliverySavedHistory(runSheets);
      }
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isCurrent()) {
        state.deliveryWorkspaceError =
          `Unable to load Saved Run Sheet history. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isDeliveryWorkspaceLoading = false;
        renderWorkspace();
      }
    }
  }

  async function updateDeliverySavedHistoryDate(nextDate) {
    state.deliverySavedHistoryDate =
      nextDate || state.deliverySavedHistoryDate || state.dispatchDate;
    if (state.workspaceRoute === "delivery/history") {
      await loadDeliverySavedHistoryData(
        state.workspaceRoute,
        state.deliverySavedHistoryDate,
      );
      return;
    }
    renderWorkspace();
  }

  function sortDeliverySavedHistory(runSheets) {
    return (runSheets || [])
      .filter((runSheet) => runSheet.status === "SAVED")
      .slice()
      .sort((left, right) =>
        String(right.delivery_date || "").localeCompare(
          String(left.delivery_date || ""),
        )
        || compareHistoryText(
          left.driver_name_snapshot || left.driver_id,
          right.driver_name_snapshot || right.driver_id,
        )
        || compareHistoryText(left.run_sheet_id, right.run_sheet_id),
      );
  }

  function compareHistoryText(left, right) {
    return String(left || "").localeCompare(String(right || ""), undefined, {
      sensitivity: "base",
    });
  }

  return {
    loadDeliverySavedHistoryData,
    updateDeliverySavedHistoryDate,
    sortDeliverySavedHistory,
    compareHistoryText,
  };
}
