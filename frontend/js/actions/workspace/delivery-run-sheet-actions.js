import {
  buildDeliveryCloseoutConfirmation,
  buildDeliveryCloseoutPayload,
  createDeliveryCloseoutDraft,
  validateDeliveryCloseoutDraft,
} from "../../utils/delivery-closeout-utils.js";

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
          dispatch_date: candidate.dispatch_date,
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

  function openDeliveryRunSheetCloseout(runSheetId) {
    const runSheet = (state.deliveryRunSheets || []).find(
      (item) => item.run_sheet_id === runSheetId,
    );
    if (
      !runSheet
      || runSheet.status !== "SAVED"
      || (runSheet.execution_status || "OPEN") !== "OPEN"
    ) {
      return;
    }
    state.deliveryRunSheetCloseout = createDeliveryCloseoutDraft(runSheet);
    state.deliveryActionError = "";
    state.deliveryActionSuccess = "";
    renderWorkspace();
  }

  function closeDeliveryRunSheetCloseout() {
    const draft = state.deliveryRunSheetCloseout;
    if (
      !draft
      || state.deliveryBusyActionKeys?.[
        `delivery-closeout:${draft.run_sheet_id}`
      ]
    ) {
      return;
    }
    state.deliveryRunSheetCloseout = null;
    renderWorkspace();
  }

  function updateDeliveryCloseoutRow(rowId, field, value) {
    const draft = state.deliveryRunSheetCloseout;
    const row = draft?.rows?.find(
      (item) => item.run_sheet_row_id === rowId,
    );
    if (!row) {
      return;
    }
    row[field] = value;
    if (field === "outcome" && value !== "RETURN_TO_POOL") {
      row.reason_code = "";
      row.note = "";
      row.next_delivery_date = "";
    }
    draft.error = "";
    return row;
  }

  function markAllDeliveryCloseoutRowsDelivered() {
    const draft = state.deliveryRunSheetCloseout;
    if (!draft) {
      return;
    }
    draft.rows.forEach((row) => {
      row.outcome = "DELIVERED";
      row.reason_code = "";
      row.note = "";
      row.next_delivery_date = "";
    });
    draft.error = "";
    return draft;
  }

  async function submitDeliveryRunSheetCloseout() {
    const draft = state.deliveryRunSheetCloseout;
    if (!draft) {
      return;
    }
    const actionKey = `delivery-closeout:${draft.run_sheet_id}`;
    if (state.deliveryBusyActionKeys?.[actionKey]) {
      return;
    }
    const error = validateDeliveryCloseoutDraft(draft);
    if (error) {
      draft.error = error;
      return { error };
    }
    if (!confirmAction(buildDeliveryCloseoutConfirmation(draft))) {
      return;
    }
    await runDeliveryAction(
      actionKey,
      async (context) => {
        const closedRunSheet = await api.closeDeliveryRunSheet(
          draft.run_sheet_id,
          buildDeliveryCloseoutPayload(draft),
        );
        if (!isDeliveryMutationCurrent(context)) {
          return;
        }
        state.deliveryRunSheetCloseout = null;
        const boardPromise = api.getDeliveryWorkspaceBoard(state.dispatchDate);
        await loadDeliveryRoute(context.route);
        const board = await boardPromise;
        if (isDeliveryMutationCurrent(context)) {
          state.deliveryBoard = board;
          const summary = closedRunSheet.closeout_summary || {};
          state.deliveryActionSuccess = [
            "Run sheet closed.",
            `${Number(summary.delivered_count || 0)} orders delivered and`,
            `${Number(summary.returned_to_pool_count || 0)} returned to the Task Pool.`,
          ].join(" ");
        }
      },
      (requestError) => {
        if (state.deliveryRunSheetCloseout) {
          state.deliveryRunSheetCloseout.error = requestError.message;
        }
      },
    );
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
    openDeliveryRunSheetCloseout,
    closeDeliveryRunSheetCloseout,
    updateDeliveryCloseoutRow,
    markAllDeliveryCloseoutRowsDelivered,
    submitDeliveryRunSheetCloseout,
    exportDeliveryRunSheet,
    exportDeliveryRunSheets,
    navigateToDeliveryRunSheets,
  };
}
