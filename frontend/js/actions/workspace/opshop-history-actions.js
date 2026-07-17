export function createOpShopHistoryActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);
  const compareHistoryText = (...args) => context.actions.compareHistoryText(...args);

  async function loadOpShopSavedHistoryData(
    route = state.workspaceRoute,
    historyDate = state.opshopSavedHistoryDate,
    requestVersion = ++context.opshopWorkspaceRequestVersion,
  ) {
    const requestedHistoryDate =
      historyDate || state.opshopSavedHistoryDate || state.dispatchDate;
    state.opshopSavedHistoryDate = requestedHistoryDate;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === "opshop/history" &&
      route === "opshop/history" &&
      state.opshopSavedHistoryDate === requestedHistoryDate &&
      requestVersion === context.opshopWorkspaceRequestVersion;

    state.opshopSavedHistoryCollections = [];
    state.isOpShopWorkspaceLoading = true;
    state.opshopWorkspaceError = "";
    state.opshopActionError = "";
    renderWorkspace();
    try {
      const collections = await api.listOpShopPickupCollectionsByPickupDate(
        requestedHistoryDate,
        "SAVED",
      );
      if (isCurrent()) {
        state.opshopSavedHistoryCollections =
          sortOpShopSavedHistory(collections);
      }
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isCurrent()) {
        state.opshopWorkspaceError =
          `Unable to load Saved Pickup Collection history. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isOpShopWorkspaceLoading = false;
        renderWorkspace();
      }
    }
  }

  async function updateOpShopSavedHistoryDate(nextDate) {
    state.opshopSavedHistoryDate =
      nextDate || state.opshopSavedHistoryDate || state.dispatchDate;
    if (state.workspaceRoute === "opshop/history") {
      await loadOpShopSavedHistoryData(
        state.workspaceRoute,
        state.opshopSavedHistoryDate,
      );
      return;
    }
    renderWorkspace();
  }

  function sortOpShopSavedHistory(collections) {
    return (collections || [])
      .filter((collection) => collection.status === "SAVED")
      .slice()
      .sort((left, right) =>
        String(right.pickup_date || "").localeCompare(
          String(left.pickup_date || ""),
        )
        || compareHistoryText(
          left.driver_name_snapshot || left.driver_id,
          right.driver_name_snapshot || right.driver_id,
        )
        || compareHistoryText(left.collection_id, right.collection_id),
      );
  }

  return {
    loadOpShopSavedHistoryData,
    updateOpShopSavedHistoryDate,
    sortOpShopSavedHistory,
  };
}
