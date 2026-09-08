import { applyDeliveryAreaClassification } from "../../utils/delivery-area-utils.js";
import {
  captureElementScroll,
  restoreElementScroll,
} from "../../utils/scroll-utils.js";


const CURRENT_FUTURE_SOURCE = "attache-current-future";
const READY_PAYMENT_ELIGIBILITIES = new Set(["NOT_REQUIRED", "PAID_IN_FULL"]);


export function createDeliveryAttacheCurrentFutureActions(context) {
  const { api, confirmAction, renderWorkspace, state } = context;

  const captureMutationContext = (...args) => context.actions.captureMutationContext(...args);
  const isDeliveryMutationCurrent = (...args) => context.actions.isDeliveryMutationCurrent(...args);
  const loadDeliveryRoute = (...args) => context.actions.loadDeliveryRoute(...args);
  const runDeliveryAction = (...args) => context.actions.runDeliveryAction(...args);

  async function loadDeliveryAttacheCurrentFutureInvoices() {
    const current = currentState();
    if (current.isLoading || current.isCommitting) {
      return;
    }
    const mutationContext = captureMutationContext();
    const requestVersion = nextRequestVersion();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      isLoading: true,
      error: "",
      success: "",
    };
    renderCurrentFuturePreservingScroll();
    try {
      const response = await api.previewDeliveryAttacheCurrentFutureInvoices();
      if (!isCurrentRequest(mutationContext, requestVersion)) {
        return;
      }
      if (
        !response
        || typeof response.from_date !== "string"
        || !Array.isArray(response.rows)
      ) {
        throw new Error("The server returned an invalid preview response.");
      }
      state.deliveryAttacheCurrentFutureImportState = {
        ...currentState(),
        hasLoaded: true,
        fromDate: response.from_date,
        rows: response.rows.map(normalizePreviewRow),
        expandedRowIds: {},
        error: "",
        success: "",
      };
    } catch (error) {
      if (!isCurrentRequest(mutationContext, requestVersion)) {
        return;
      }
      state.deliveryAttacheCurrentFutureImportState = {
        ...currentState(),
        error: `Unable to load Today & Future Attaché invoices. ${error.message}`,
      };
    } finally {
      if (isCurrentRequest(mutationContext, requestVersion)) {
        state.deliveryAttacheCurrentFutureImportState = {
          ...currentState(),
          isLoading: false,
        };
        renderCurrentFuturePreservingScroll();
      }
    }
  }

  async function refreshDeliveryAttacheCurrentFutureInvoices() {
    const current = currentState();
    if (current.isLoading || current.isCommitting) {
      return;
    }
    if (
      (current.rows || []).length
      && !confirmAction(
        "Reload invoices from Attaché? Current preview edits will be discarded.",
      )
    ) {
      return;
    }
    await loadDeliveryAttacheCurrentFutureInvoices();
  }

  function updateDeliveryAttacheCurrentFutureImportRow(rowId, field, value) {
    const current = currentState();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      rows: (current.rows || []).map((row) =>
        row.row_id === rowId ? { ...row, [field]: value } : row),
    };
  }

  function updateDeliveryAttacheCurrentFutureProductLine(
    rowId,
    lineIndex,
    field,
    value,
  ) {
    const current = currentState();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId) {
          return row;
        }
        const productLines = [...(row.product_lines || [])];
        productLines[lineIndex] = {
          ...(productLines[lineIndex] || emptyProductLine()),
          [field]: ["quantity", "package_quantity"].includes(field)
            ? (value === "" ? "" : Number(value))
            : value,
        };
        return { ...row, product_lines: productLines };
      }),
    };
  }

  function addDeliveryAttacheCurrentFutureProductLine(rowId) {
    const current = currentState();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      rows: (current.rows || []).map((row) => row.row_id === rowId
        ? {
          ...row,
          product_lines: [...(row.product_lines || []), emptyProductLine()],
        }
        : row),
    };
    renderCurrentFuturePreservingScroll();
  }

  function removeDeliveryAttacheCurrentFutureProductLine(rowId, lineIndex) {
    const current = currentState();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      rows: (current.rows || []).map((row) => row.row_id === rowId
        ? {
          ...row,
          product_lines: (row.product_lines || []).filter(
            (_line, index) => index !== lineIndex,
          ),
        }
        : row),
    };
    renderCurrentFuturePreservingScroll();
  }

  function toggleDeliveryAttacheCurrentFutureRow(rowId, selected) {
    const current = currentState();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId || row.is_duplicate || !row.importable) {
          return row;
        }
        return { ...row, selected };
      }),
    };
    renderCurrentFuturePreservingScroll();
  }

  function toggleDeliveryAttacheCurrentFutureExpanded(rowId) {
    const current = currentState();
    const expandedRowIds = { ...(current.expandedRowIds || {}) };
    if (expandedRowIds[rowId]) {
      delete expandedRowIds[rowId];
    } else {
      expandedRowIds[rowId] = true;
    }
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      expandedRowIds,
    };
    return state.deliveryAttacheCurrentFutureImportState;
  }

  function selectAllReadyDeliveryAttacheCurrentFutureRows() {
    const current = currentState();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({
        ...row,
        selected: Boolean(
          row.importable
          && !row.is_duplicate
          && !(row.warnings || []).length
          && isPaymentEligible(row),
        ),
      })),
    };
    renderCurrentFuturePreservingScroll();
  }

  function clearDeliveryAttacheCurrentFutureSelection() {
    const current = currentState();
    state.deliveryAttacheCurrentFutureImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({ ...row, selected: false })),
    };
    renderCurrentFuturePreservingScroll();
  }

  function updateDeliveryAttacheCurrentFutureSearch(value) {
    state.deliveryAttacheCurrentFutureImportState = {
      ...currentState(),
      search: String(value || ""),
    };
  }

  function updateDeliveryAttacheCurrentFutureFilter(value) {
    state.deliveryAttacheCurrentFutureImportState = {
      ...currentState(),
      filter: String(value || "ALL"),
    };
  }

  async function classifyDeliveryAttacheCurrentFutureRow(rowId) {
    const row = (currentState().rows || []).find(
      (candidate) => candidate.row_id === rowId,
    );
    if (!row) {
      return;
    }
    const suburb = String(row.suburb || "");
    const postcode = String(row.postcode || "");
    const versions = context.deliveryAttacheCurrentFutureAreaClassificationVersions
      || (context.deliveryAttacheCurrentFutureAreaClassificationVersions = {});
    const requestVersion = Number(versions[rowId] || 0) + 1;
    versions[rowId] = requestVersion;
    const mutationContext = captureMutationContext();
    const isCurrent = () => {
      const latest = (currentState().rows || []).find(
        (candidate) => candidate.row_id === rowId,
      );
      return isCurrentSource(mutationContext)
        && versions[rowId] === requestVersion
        && String(latest?.suburb || "") === suburb
        && String(latest?.postcode || "") === postcode;
    };
    try {
      const classification = suburb.trim()
        ? await api.classifyDeliveryArea(suburb, postcode)
        : {
            known: false,
            auto_delivery_region: null,
            auto_delivery_area: null,
            delivery_area: null,
          };
      if (!isCurrent()) {
        return;
      }
      state.deliveryAttacheCurrentFutureImportState = {
        ...currentState(),
        rows: currentState().rows.map((candidate) =>
          candidate.row_id === rowId
            ? applyDeliveryAreaClassification(candidate, classification)
            : candidate),
        error: "",
      };
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      state.deliveryAttacheCurrentFutureImportState = {
        ...currentState(),
        error: `Unable to classify Delivery Area. ${error.message}`,
      };
    }
    renderCurrentFuturePreservingScroll();
  }

  async function commitDeliveryAttacheCurrentFutureImport() {
    const current = currentState();
    const selectedRows = (current.rows || []).filter(
      (row) => row.selected && row.importable && !row.is_duplicate,
    );
    if (!selectedRows.length) {
      state.deliveryAttacheCurrentFutureImportState = {
        ...current,
        error: "Select at least one non-duplicate invoice to import.",
      };
      renderCurrentFuturePreservingScroll();
      return;
    }
    const requestVersion = nextRequestVersion();
    let actionContext = null;
    await runDeliveryAction("delivery-attache-current-future-import", async (mutationContext) => {
      actionContext = mutationContext;
      if (!isCurrentRequest(mutationContext, requestVersion)) {
        return;
      }
      state.deliveryAttacheCurrentFutureImportState = {
        ...currentState(),
        isCommitting: true,
        error: "",
        success: "",
      };
      renderCurrentFuturePreservingScroll();
      const response = await api.commitDeliveryAttacheCurrentFutureInvoices({
        rows: currentState().rows || [],
        from_date: currentState().fromDate,
      });
      if (!isCurrentRequest(mutationContext, requestVersion)) {
        return;
      }
      state.deliveryAttacheCurrentFutureImportState = {
        ...currentState(),
        isCommitting: false,
        rows: (currentState().rows || []).map((row) =>
          row.selected ? { ...row, selected: false } : row),
        success:
          `Imported ${response.imported_count || 0} Delivery Orders. `
          + `${response.skipped_count || 0} rows skipped.`,
        error: (response.skipped_rows || []).some((row) => row.refresh_required)
          ? "Some invoice previews expired or could not be verified. Refresh Today & Future Invoices before importing."
          : "",
      };
      await loadDeliveryRoute(mutationContext.route);
    }, (error) => {
      if (!isCurrentRequest(actionContext, requestVersion)) {
        return;
      }
      state.deliveryAttacheCurrentFutureImportState = {
        ...currentState(),
        isCommitting: false,
        error: `Unable to import Today & Future Attaché invoices. ${error.message}`,
      };
    });
  }

  function hasDeliveryAttacheCurrentFutureDraft() {
    const current = currentState();
    return Boolean(
      !current.success
      && (current.hasLoaded || (current.rows || []).length),
    );
  }

  function invalidateDeliveryAttacheCurrentFutureRequests() {
    nextRequestVersion();
    context.deliveryAttacheCurrentFutureAreaClassificationVersions = {};
    const current = currentState();
    if (current.isLoading || current.isCommitting) {
      state.deliveryAttacheCurrentFutureImportState = {
        ...current,
        isLoading: false,
        isCommitting: false,
      };
    }
  }

  function resetDeliveryAttacheCurrentFutureState() {
    invalidateDeliveryAttacheCurrentFutureRequests();
    state.deliveryAttacheCurrentFutureImportState =
      defaultDeliveryAttacheCurrentFutureImportState();
  }

  function defaultDeliveryAttacheCurrentFutureImportState() {
    return {
      isLoading: false,
      isCommitting: false,
      hasLoaded: false,
      fromDate: "",
      rows: [],
      expandedRowIds: {},
      search: "",
      filter: "ALL",
      error: "",
      success: "",
    };
  }

  function currentState() {
    return state.deliveryAttacheCurrentFutureImportState
      || defaultDeliveryAttacheCurrentFutureImportState();
  }

  function nextRequestVersion() {
    context.deliveryAttacheCurrentFutureRequestVersion = Number(
      context.deliveryAttacheCurrentFutureRequestVersion || 0,
    ) + 1;
    return context.deliveryAttacheCurrentFutureRequestVersion;
  }

  function isCurrentSource(mutationContext) {
    return isDeliveryMutationCurrent(mutationContext)
      && state.workspaceRoute === "delivery/task-pool"
      && state.deliveryAttacheImportState?.isOpen
      && state.deliveryDocumentImportState?.isOpen
      && state.deliveryDocumentImportState?.source === CURRENT_FUTURE_SOURCE;
  }

  function isCurrentRequest(mutationContext, requestVersion) {
    return isCurrentSource(mutationContext)
      && requestVersion === context.deliveryAttacheCurrentFutureRequestVersion;
  }

  function normalizePreviewRow(row) {
    const importable = Boolean(row?.importable && isPaymentEligible(row));
    return {
      ...row,
      importable,
      selected: Boolean(
        importable
        && !row?.is_duplicate
        && !(row?.warnings || []).length
        && row?.selected !== false,
      ),
    };
  }

  function isPaymentEligible(row) {
    return READY_PAYMENT_ELIGIBILITIES.has(row?.payment_eligibility);
  }

  function emptyProductLine() {
    return {
      product_code: "",
      product_name: "",
      quantity: 0,
      unit: "KG",
      package_quantity: "",
      package_unit: "",
    };
  }

  function renderCurrentFuturePreservingScroll() {
    const snapshot = typeof document === "undefined"
      ? null
      : captureElementScroll(".workspace-modal-body");
    renderWorkspace();
    restoreElementScroll(snapshot);
  }

  return {
    loadDeliveryAttacheCurrentFutureInvoices,
    refreshDeliveryAttacheCurrentFutureInvoices,
    updateDeliveryAttacheCurrentFutureImportRow,
    updateDeliveryAttacheCurrentFutureProductLine,
    addDeliveryAttacheCurrentFutureProductLine,
    removeDeliveryAttacheCurrentFutureProductLine,
    toggleDeliveryAttacheCurrentFutureRow,
    toggleDeliveryAttacheCurrentFutureExpanded,
    selectAllReadyDeliveryAttacheCurrentFutureRows,
    clearDeliveryAttacheCurrentFutureSelection,
    updateDeliveryAttacheCurrentFutureSearch,
    updateDeliveryAttacheCurrentFutureFilter,
    classifyDeliveryAttacheCurrentFutureRow,
    commitDeliveryAttacheCurrentFutureImport,
    hasDeliveryAttacheCurrentFutureDraft,
    invalidateDeliveryAttacheCurrentFutureRequests,
    resetDeliveryAttacheCurrentFutureState,
    defaultDeliveryAttacheCurrentFutureImportState,
  };
}
