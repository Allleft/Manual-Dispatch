export function createWorkspaceStateReset(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadWorkspaceRoute = (...args) => context.actions.loadWorkspaceRoute(...args);
  const invalidateDeliveryAttachePreview = (...args) => context.actions.invalidateDeliveryAttachePreview(...args);
  const defaultDeliveryAttacheImportState = (...args) => context.actions.defaultDeliveryAttacheImportState(...args);

  async function updateDispatchDate(nextDate) {
    if (!nextDate || nextDate === state.dispatchDate) {
      return;
    }
    clearWorkspaceDraftsForDispatchDateChange();
    state.dispatchDate = nextDate;
    await loadWorkspaceRoute(state.workspaceRoute);
  }

  function saveSnapshotPayload() {
    return {
      saved_by_account_name: state.accountName || null,
      saved_by_account_id: state.accountId || null,
    };
  }

  function clearWorkspaceDraftsForDispatchDateChange() {
    invalidateDeliveryAttachePreview();
    state.deliveryAssignmentDrafts = {};
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
    state.opshopAssignmentDrafts = {};
    state.opshopCollectionEntryDrafts = {};
    state.opshopCollectionEntryDraftVersions = {};
    state.countrysideRouteGroupDrafts = {};
    state.collapsedRegularOpShopPickupDates = {};
    state.deliveryActionError = "";
    state.opshopActionError = "";
  }

  function clearGenerationConfirmationsForRoute(route) {
    if (route !== "delivery/trip-summary") {
      state.deliveryGenerationConfirmation = null;
    }
    if (route !== "opshop/trip-summary") {
      state.opshopGenerationConfirmation = null;
    }
  }

  return {
    updateDispatchDate,
    saveSnapshotPayload,
    clearWorkspaceDraftsForDispatchDateChange,
    clearGenerationConfirmationsForRoute,
  };
}
