import { applyDeliveryAreaClassification } from "../../utils/delivery-area-utils.js";
import {
  captureElementScroll,
  restoreElementScroll,
} from "../../utils/scroll-utils.js";

const MAX_DELIVERY_DOCKET_IMPORT_FILES = 30;

export function createDeliveryDocketActions(context) {
  const { api, renderWorkspace, state } = context;

  const loadDeliveryRoute = (...args) => context.actions.loadDeliveryRoute(...args);
  const runDeliveryAction = (...args) => context.actions.runDeliveryAction(...args);
  const captureMutationContext = (...args) => context.actions.captureMutationContext(...args);
  const isDeliveryMutationCurrent = (...args) => context.actions.isDeliveryMutationCurrent(...args);

  function updateDeliveryDocketImportFiles(files, { source = "chooser" } = {}) {
    invalidateDeliveryDocketPreview();
    const selectedFiles = Array.from(files || []);
    if (selectedFiles.length > MAX_DELIVERY_DOCKET_IMPORT_FILES) {
      state.deliveryDocketImportState = {
        ...(state.deliveryDocketImportState || defaultDeliveryDocketImportState()),
        files: [],
        rows: [],
        step: "files",
        expandedRowIds: {},
        error: "You can import up to 30 files at a time.",
        success: "",
      };
      renderWorkspace();
      return;
    }
    const docxFiles = selectedFiles.filter(isDocxFile);
    const rejectedCount = selectedFiles.length - docxFiles.length;
    let error = "";
    if (selectedFiles.length && !docxFiles.length) {
      error = source === "drop"
        ? "No DOCX files were dropped. Drop one or more Delivery Docket DOCX files."
        : "No DOCX files were selected. Choose one or more Delivery Docket DOCX files.";
    } else if (rejectedCount) {
      error = `${rejectedCount} non-DOCX file${rejectedCount === 1 ? " was" : "s were"} ignored.`;
    }
    state.deliveryDocketImportState = {
      ...(state.deliveryDocketImportState || defaultDeliveryDocketImportState()),
      files: docxFiles,
      rows: [],
      step: "files",
      expandedRowIds: {},
      error,
      success: "",
    };
    renderWorkspace();
  }

  function removeDeliveryDocketImportFile(index) {
    invalidateDeliveryDocketPreview();
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      files: (current.files || []).filter((_file, fileIndex) => fileIndex !== index),
      rows: [],
      step: "files",
      expandedRowIds: {},
      error: "",
      success: "",
    };
    renderWorkspace();
  }

  async function previewDeliveryDocketImport() {
    const importState = state.deliveryDocketImportState || {};
    if (importState.isPreviewing || !(importState.files || []).length) {
      return;
    }
    const mutationContext = captureMutationContext();
    const requestVersion = ++context.deliveryDocketPreviewRequestVersion;
    const isCurrent = () =>
      isDeliveryMutationCurrent(mutationContext)
      && state.workspaceRoute === "delivery/task-pool"
      && state.deliveryAttacheImportState?.isOpen
      && state.deliveryDocumentImportState?.source === "docket"
      && requestVersion === context.deliveryDocketPreviewRequestVersion;
    state.deliveryDocketImportState = {
      ...importState,
      isPreviewing: true,
      step: "files",
      error: "",
      success: "",
    };
    renderWorkspace();
    try {
      const response = await api.previewDeliveryDockets(importState.files);
      if (!isCurrent()) {
        return;
      }
      state.deliveryDocketImportState = {
        ...state.deliveryDocketImportState,
        step: "review",
        rows: (response.rows || []).map((row) => ({
          ...row,
          selected: Boolean(row.selected && row.importable && !row.is_duplicate),
        })),
        expandedRowIds: {},
      };
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      state.deliveryDocketImportState = {
        ...state.deliveryDocketImportState,
        error: `Unable to preview Delivery Dockets. ${error.message}`,
      };
    } finally {
      if (isCurrent()) {
        state.deliveryDocketImportState = {
          ...state.deliveryDocketImportState,
          isPreviewing: false,
        };
        renderWorkspace();
      }
    }
  }

  function backDeliveryDocketImportToFiles() {
    invalidateDeliveryDocketPreview();
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      step: "files",
      rows: [],
      expandedRowIds: {},
      error: "",
      success: "",
    };
    renderWorkspace();
  }

  function updateDeliveryDocketImportRow(rowId, field, value) {
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      rows: (current.rows || []).map((row) =>
        row.row_id === rowId ? { ...row, [field]: value } : row,
      ),
    };
  }

  async function classifyDeliveryDocketImportRow(rowId) {
    const importState = state.deliveryDocketImportState || {};
    const row = (importState.rows || []).find((candidate) => candidate.row_id === rowId);
    if (!row) {
      return;
    }
    const suburb = String(row.suburb || "");
    const postcode = String(row.postcode || "");
    const versions = context.deliveryDocketAreaClassificationVersions;
    const requestVersion = (versions[rowId] || 0) + 1;
    versions[rowId] = requestVersion;
    const mutationContext = captureMutationContext();
    const isCurrent = () => {
      const latest = (state.deliveryDocketImportState?.rows || []).find(
        (candidate) => candidate.row_id === rowId,
      );
      return isDeliveryMutationCurrent(mutationContext)
        && state.workspaceRoute === "delivery/task-pool"
        && state.deliveryAttacheImportState?.isOpen
        && state.deliveryDocumentImportState?.source === "docket"
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
      state.deliveryDocketImportState = {
        ...state.deliveryDocketImportState,
        rows: state.deliveryDocketImportState.rows.map((candidate) =>
          candidate.row_id === rowId
            ? applyDeliveryAreaClassification(candidate, classification)
            : candidate,
        ),
        error: "",
      };
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      state.deliveryDocketImportState = {
        ...state.deliveryDocketImportState,
        error: `Unable to classify Delivery Area. ${error.message}`,
      };
    }
    renderDeliveryDocketImportPreservingScroll();
  }

  function renderDeliveryDocketImportPreservingScroll() {
    const snapshot = typeof document === "undefined"
      ? null
      : captureElementScroll(".workspace-modal-body");
    renderWorkspace();
    restoreElementScroll(snapshot);
  }

  function updateDeliveryDocketImportProductLine(rowId, lineIndex, field, value) {
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
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

  function addDeliveryDocketImportProductLine(rowId) {
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      rows: (current.rows || []).map((row) => row.row_id === rowId
        ? { ...row, product_lines: [...(row.product_lines || []), emptyProductLine()] }
        : row),
    };
    renderWorkspace();
  }

  function removeDeliveryDocketImportProductLine(rowId, lineIndex) {
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      rows: (current.rows || []).map((row) => row.row_id === rowId
        ? {
          ...row,
          product_lines: (row.product_lines || []).filter((_line, index) => index !== lineIndex),
        }
        : row),
    };
    renderWorkspace();
  }

  function toggleDeliveryDocketImportRow(rowId, selected) {
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId || row.is_duplicate || !row.importable) {
          return row;
        }
        return { ...row, selected };
      }),
    };
    renderWorkspace();
  }

  function toggleDeliveryDocketImportExpanded(rowId) {
    const current = state.deliveryDocketImportState || {};
    const expandedRowIds = { ...(current.expandedRowIds || {}) };
    if (expandedRowIds[rowId]) {
      delete expandedRowIds[rowId];
    } else {
      expandedRowIds[rowId] = true;
    }
    state.deliveryDocketImportState = { ...current, expandedRowIds };
    return state.deliveryDocketImportState;
  }

  function selectAllReadyDeliveryDocketRows() {
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({
        ...row,
        selected: Boolean(row.importable && !row.is_duplicate),
      })),
    };
    renderWorkspace();
  }

  function clearDeliveryDocketImportSelection() {
    const current = state.deliveryDocketImportState || {};
    state.deliveryDocketImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({ ...row, selected: false })),
    };
    renderWorkspace();
  }

  function updateDeliveryDocketReviewSearch(value) {
    state.deliveryDocketImportState = {
      ...(state.deliveryDocketImportState || {}),
      search: String(value || ""),
    };
  }

  function updateDeliveryDocketReviewFilter(value) {
    state.deliveryDocketImportState = {
      ...(state.deliveryDocketImportState || {}),
      filter: String(value || "ALL"),
    };
  }

  async function commitDeliveryDocketImport() {
    const importState = state.deliveryDocketImportState || {};
    const selectedRows = (importState.rows || []).filter((row) => row.selected);
    if (!selectedRows.length) {
      state.deliveryDocketImportState = {
        ...importState,
        error: "Select at least one importable Delivery Docket to import.",
      };
      renderWorkspace();
      return;
    }
    await runDeliveryAction("delivery-docket-import", async (mutationContext) => {
      state.deliveryDocketImportState = {
        ...state.deliveryDocketImportState,
        isCommitting: true,
        error: "",
        success: "",
      };
      renderWorkspace();
      const response = await api.commitDeliveryDockets({
        rows: state.deliveryDocketImportState.rows || [],
      });
      if (
        isDeliveryMutationCurrent(mutationContext)
        && state.deliveryAttacheImportState?.isOpen
        && state.deliveryDocumentImportState?.source === "docket"
      ) {
        state.deliveryDocketImportState = {
          ...state.deliveryDocketImportState,
          isCommitting: false,
          rows: (state.deliveryDocketImportState.rows || []).map((row) =>
            row.selected ? { ...row, selected: false } : row,
          ),
          success:
            `Imported ${response.imported_count || 0} Delivery Orders. `
            + `${response.skipped_count || 0} rows skipped.`,
        };
        await loadDeliveryRoute(mutationContext.route);
      }
    }, (error) => {
      state.deliveryDocketImportState = {
        ...state.deliveryDocketImportState,
        isCommitting: false,
        error: `Unable to import Delivery Dockets. ${error.message}`,
      };
    });
  }

  function hasDeliveryDocketDraft() {
    const current = state.deliveryDocketImportState || {};
    return Boolean(
      !current.success
      && ((current.files || []).length || (current.rows || []).length),
    );
  }

  function invalidateDeliveryDocketPreview() {
    context.deliveryDocketPreviewRequestVersion += 1;
  }

  function defaultDeliveryDocketImportState() {
    return {
      isPreviewing: false,
      isCommitting: false,
      step: "files",
      files: [],
      rows: [],
      expandedRowIds: {},
      search: "",
      filter: "ALL",
      error: "",
      success: "",
    };
  }

  function isDocxFile(file) {
    if (!file) {
      return false;
    }
    const name = String(file.name || "").toLowerCase();
    const type = String(file.type || "").toLowerCase();
    return name.endsWith(".docx") && [
      "",
      "application/octet-stream",
      "application/zip",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ].includes(type);
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

  return {
    updateDeliveryDocketImportFiles,
    removeDeliveryDocketImportFile,
    previewDeliveryDocketImport,
    backDeliveryDocketImportToFiles,
    updateDeliveryDocketImportRow,
    classifyDeliveryDocketImportRow,
    updateDeliveryDocketImportProductLine,
    addDeliveryDocketImportProductLine,
    removeDeliveryDocketImportProductLine,
    toggleDeliveryDocketImportRow,
    toggleDeliveryDocketImportExpanded,
    selectAllReadyDeliveryDocketRows,
    clearDeliveryDocketImportSelection,
    updateDeliveryDocketReviewSearch,
    updateDeliveryDocketReviewFilter,
    commitDeliveryDocketImport,
    hasDeliveryDocketDraft,
    invalidateDeliveryDocketPreview,
    defaultDeliveryDocketImportState,
    isDocxFile,
  };
}
