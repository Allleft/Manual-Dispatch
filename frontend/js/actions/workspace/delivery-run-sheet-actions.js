export function createDeliveryRunSheetActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadDeliveryRoute = (...args) => context.actions.loadDeliveryRoute(...args);
  const runDeliveryAction = (...args) => context.actions.runDeliveryAction(...args);
  const saveSnapshotPayload = (...args) => context.actions.saveSnapshotPayload(...args);
  const isDeliveryGenerationBusy = (...args) => context.actions.isDeliveryGenerationBusy(...args);
  const restoreGenerateButtonFocus = (...args) => context.actions.restoreGenerateButtonFocus(...args);
  const isDeliveryMutationCurrent = (...args) => context.actions.isDeliveryMutationCurrent(...args);

  function generateDeliveryRunSheet(candidate) {
    if (!candidate || !(candidate.orders || []).length) {
      return;
    }
    state.deliveryGenerationConfirmation = {
      ...candidate,
      dispatch_date: state.dispatchDate,
      error: "",
      orders: (candidate.orders || []).map((order) => ({ ...order })),
      totals: { ...(candidate.totals || {}) },
      vehicle: candidate.vehicle ? { ...candidate.vehicle } : null,
    };
    state.deliveryActionError = "";
    renderWorkspace();
  }

  function closeDeliveryGenerationConfirmation() {
    const confirmation = state.deliveryGenerationConfirmation;
    if (!confirmation || isDeliveryGenerationBusy(confirmation)) {
      return;
    }
    state.deliveryGenerationConfirmation = null;
    renderWorkspace();
    restoreGenerateButtonFocus("delivery", confirmation);
  }

  async function confirmGenerateDeliveryRunSheet() {
    const candidate = state.deliveryGenerationConfirmation;
    if (!candidate || isDeliveryGenerationBusy(candidate)) {
      return;
    }
    await runDeliveryAction(
      `delivery-generate:${candidate.delivery_date}:${candidate.driver_id}`,
      async (context) => {
        await api.createGeneratedDeliveryRunSheet({
          delivery_date: candidate.delivery_date,
          driver_id: candidate.driver_id,
        });
        if (isDeliveryMutationCurrent(context)) {
          state.deliveryGenerationConfirmation = null;
          await navigateToDeliveryRunSheets();
        }
      },
      (error) => {
        state.deliveryGenerationConfirmation = {
          ...candidate,
          error: error.message,
        };
      },
    );
  }

  async function saveDeliveryRunSheet(runSheetId) {
    await runDeliveryAction(`delivery-save:${runSheetId}`, async (context) => {
      await api.saveGeneratedDeliveryRunSheet(runSheetId, saveSnapshotPayload());
      if (isDeliveryMutationCurrent(context)) {
        await loadDeliveryRoute(context.route);
      }
    });
  }

  async function cancelDeliveryRunSheet(runSheetId) {
    const confirmed = confirmAction(
      "Cancel this generated Delivery Run Sheet? Captured orders will return to the Delivery Task Pool.",
    );
    if (!confirmed) {
      return;
    }
    await runDeliveryAction(`delivery-cancel:${runSheetId}`, async (context) => {
      await api.cancelGeneratedDeliveryRunSheet(runSheetId);
      if (isDeliveryMutationCurrent(context)) {
        await loadDeliveryRoute(context.route);
      }
    });
  }

  async function exportDeliveryRunSheet(runSheetId) {
    await runDeliveryAction(`delivery-export:${runSheetId}`, async () => {
      await api.exportDeliveryRunSheetExcel(runSheetId);
    });
  }

  async function exportDeliveryRunSheets(deliveryDate) {
    const scopedDate = deliveryDate || state.deliveryTripSummaryDate || state.dispatchDate;
    const actionKey = `delivery-export-date:${scopedDate}`;
    if (state.deliveryBusyActionKeys?.[actionKey]) {
      return;
    }
    await runDeliveryAction(actionKey, async () => {
      await api.exportDeliveryRunSheetsExcel(scopedDate);
    });
  }

  async function navigateToDeliveryRunSheets() {
    if (typeof navigateWorkspaceRoute === "function") {
      await navigateWorkspaceRoute("delivery/run-sheet");
      return;
    }
    state.workspaceRoute = "delivery/run-sheet";
    state.activeWorkspace = "delivery";
    await loadDeliveryRoute("delivery/run-sheet");
  }

  return {
    generateDeliveryRunSheet,
    closeDeliveryGenerationConfirmation,
    confirmGenerateDeliveryRunSheet,
    saveDeliveryRunSheet,
    cancelDeliveryRunSheet,
    exportDeliveryRunSheet,
    exportDeliveryRunSheets,
    navigateToDeliveryRunSheets,
  };
}
