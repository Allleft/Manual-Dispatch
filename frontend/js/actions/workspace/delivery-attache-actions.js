const MAX_ATTACHE_IMPORT_FILES = 30;

export function createDeliveryAttacheActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadDeliveryRoute = (...args) => context.actions.loadDeliveryRoute(...args);
  const runDeliveryAction = (...args) => context.actions.runDeliveryAction(...args);
  const captureMutationContext = (...args) => context.actions.captureMutationContext(...args);
  const isDeliveryMutationCurrent = (...args) => context.actions.isDeliveryMutationCurrent(...args);

  function openDeliveryAttacheImport() {
    invalidateDeliveryAttachePreview();
    context.actions.invalidateDeliveryDocketPreview?.();
    state.deliveryAttacheImportState = {
      ...defaultDeliveryAttacheImportState(),
      isOpen: true,
    };
    state.deliveryDocumentImportState = {
      isOpen: true,
      source: "chooser",
    };
    state.deliveryDocketImportState = context.actions.defaultDeliveryDocketImportState?.()
      || defaultDeliveryDocketImportStateFallback();
    renderWorkspace();
  }

  function closeDeliveryAttacheImport() {
    const hasDocketDraft = context.actions.hasDeliveryDocketDraft?.() || false;
    if (
      (hasDeliveryAttacheDraft() || hasDocketDraft)
      && !confirmAction("Discard the current Delivery Document import?")
    ) {
      return;
    }
    invalidateDeliveryAttachePreview();
    context.actions.invalidateDeliveryDocketPreview?.();
    state.deliveryAttacheImportState = defaultDeliveryAttacheImportState();
    state.deliveryDocumentImportState = {
      isOpen: false,
      source: "chooser",
    };
    state.deliveryDocketImportState = context.actions.defaultDeliveryDocketImportState?.()
      || defaultDeliveryDocketImportStateFallback();
    renderWorkspace();
  }

  function chooseDeliveryImportSource(source) {
    if (!["attache", "docket"].includes(source)) {
      return;
    }
    state.deliveryDocumentImportState = {
      isOpen: true,
      source,
    };
    renderWorkspace();
  }

  function backDeliveryImportToSources() {
    invalidateDeliveryAttachePreview();
    context.actions.invalidateDeliveryDocketPreview?.();
    state.deliveryDocumentImportState = {
      isOpen: true,
      source: "chooser",
    };
    renderWorkspace();
  }

  function updateDeliveryAttacheImportFiles(files, { source = "chooser" } = {}) {
    invalidateDeliveryAttachePreview();
    const selectedFiles = Array.from(files || []);
    if (selectedFiles.length > MAX_ATTACHE_IMPORT_FILES) {
      state.deliveryAttacheImportState = {
        ...(state.deliveryAttacheImportState || defaultDeliveryAttacheImportState()),
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
    const pdfFiles = selectedFiles.filter(isPdfFile);
    const rejectedCount = selectedFiles.length - pdfFiles.length;
    let error = "";
    if (selectedFiles.length && !pdfFiles.length) {
      error = source === "drop"
        ? "No PDF files were dropped. Drop one or more PDF files."
        : "No PDF files were selected. Choose one or more PDF files.";
    } else if (rejectedCount) {
      error = `${rejectedCount} non-PDF file${rejectedCount === 1 ? " was" : "s were"} ignored.`;
    }
    state.deliveryAttacheImportState = {
      ...state.deliveryAttacheImportState,
      files: pdfFiles,
      rows: [],
      step: "files",
      expandedRowIds: {},
      error,
      success: "",
    };
    renderWorkspace();
  }

  function removeDeliveryAttacheImportFile(index) {
    invalidateDeliveryAttachePreview();
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
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

  async function previewDeliveryAttacheImport() {
    const importState = state.deliveryAttacheImportState || {};
    if (importState.isPreviewing || !(importState.files || []).length) {
      return;
    }
    const mutationContext = captureMutationContext();
    const requestVersion = ++context.deliveryAttachePreviewRequestVersion;
    const isCurrent = () =>
      isDeliveryMutationCurrent(mutationContext) &&
      state.workspaceRoute === "delivery/task-pool" &&
      state.deliveryAttacheImportState?.isOpen &&
      requestVersion === context.deliveryAttachePreviewRequestVersion;
    state.deliveryAttacheImportState = {
      ...importState,
      isPreviewing: true,
      step: "files",
      error: "",
      success: "",
    };
    renderWorkspace();
    try {
      const response = await api.previewDeliveryAttacheInvoices(importState.files);
      if (!isCurrent()) {
        return;
      }
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
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
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        error: `Unable to preview Attache invoices. ${error.message}`,
      };
    } finally {
      if (isCurrent()) {
        state.deliveryAttacheImportState = {
          ...state.deliveryAttacheImportState,
          isPreviewing: false,
        };
        renderWorkspace();
      }
    }
  }

  function backDeliveryAttacheImportToFiles() {
    invalidateDeliveryAttachePreview();
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      step: "files",
      rows: [],
      expandedRowIds: {},
      error: "",
      success: "",
    };
    renderWorkspace();
  }

  function updateDeliveryAttacheImportRow(rowId, field, value) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) =>
        row.row_id === rowId ? { ...row, [field]: value } : row,
      ),
    };
  }

  function updateDeliveryAttacheImportProductLine(rowId, lineIndex, field, value) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId) {
          return row;
        }
        const productLines = [...(row.product_lines || [])];
        productLines[lineIndex] = {
          ...(productLines[lineIndex] || {
            product_code: "",
            product_name: "",
            quantity: 0,
            unit: "KG",
            package_quantity: "",
            package_unit: "",
          }),
          [field]: ["quantity", "package_quantity"].includes(field)
            ? (value === "" ? "" : Number(value))
            : value,
        };
        return { ...row, product_lines: productLines };
      }),
    };
  }

  function addDeliveryAttacheImportProductLine(rowId) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId) {
          return row;
        }
        return {
          ...row,
          product_lines: [
            ...(row.product_lines || []),
            {
              product_code: "",
              product_name: "",
              quantity: 0,
              unit: "KG",
              package_quantity: "",
              package_unit: "",
            },
          ],
        };
      }),
    };
    renderWorkspace();
  }

  function removeDeliveryAttacheImportProductLine(rowId, lineIndex) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId) {
          return row;
        }
        return {
          ...row,
          product_lines: (row.product_lines || []).filter(
            (_line, index) => index !== lineIndex,
          ),
        };
      }),
    };
    renderWorkspace();
  }

  function toggleDeliveryAttacheImportRow(rowId, selected) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
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

  function toggleDeliveryAttacheImportExpanded(rowId) {
    const current = state.deliveryAttacheImportState || {};
    const expandedRowIds = { ...(current.expandedRowIds || {}) };
    if (expandedRowIds[rowId]) {
      delete expandedRowIds[rowId];
    } else {
      expandedRowIds[rowId] = true;
    }
    state.deliveryAttacheImportState = {
      ...current,
      expandedRowIds,
    };
    return state.deliveryAttacheImportState;
  }

  function selectAllReadyDeliveryAttacheRows() {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({
        ...row,
        selected: Boolean(row.importable && !row.is_duplicate),
      })),
    };
    renderWorkspace();
  }

  function clearDeliveryAttacheImportSelection() {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({ ...row, selected: false })),
    };
    renderWorkspace();
  }

  function updateDeliveryAttacheReviewSearch(value) {
    state.deliveryAttacheImportState = {
      ...(state.deliveryAttacheImportState || {}),
      search: String(value || ""),
    };
  }

  function updateDeliveryAttacheReviewFilter(value) {
    state.deliveryAttacheImportState = {
      ...(state.deliveryAttacheImportState || {}),
      filter: String(value || "ALL"),
    };
  }

  async function commitDeliveryAttacheImport() {
    const importState = state.deliveryAttacheImportState || {};
    const selectedRows = (importState.rows || []).filter((row) => row.selected);
    if (!selectedRows.length) {
      state.deliveryAttacheImportState = {
        ...importState,
        error: "Select at least one non-duplicate invoice to import.",
      };
      renderWorkspace();
      return;
    }
    await runDeliveryAction("delivery-attache-import", async (context) => {
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        isCommitting: true,
        error: "",
        success: "",
      };
      renderWorkspace();
      const response = await api.commitDeliveryAttacheInvoices({
        rows: state.deliveryAttacheImportState.rows || [],
      });
      if (isDeliveryMutationCurrent(context) && state.deliveryAttacheImportState?.isOpen) {
        state.deliveryAttacheImportState = {
          ...state.deliveryAttacheImportState,
          isCommitting: false,
          rows: (state.deliveryAttacheImportState.rows || []).map((row) =>
            row.selected ? { ...row, selected: false } : row,
          ),
          success:
            `Imported ${response.imported_count || 0} Delivery Orders. `
            + `${response.skipped_count || 0} rows skipped.`,
        };
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        isCommitting: false,
        error: `Unable to import Attache invoices. ${error.message}`,
      };
    });
  }

  function hasDeliveryAttacheDraft() {
    const current = state.deliveryAttacheImportState || {};
    return Boolean(
      current.isOpen &&
      !current.success &&
      ((current.files || []).length || (current.rows || []).length),
    );
  }

  function invalidateDeliveryAttachePreview() {
    context.deliveryAttachePreviewRequestVersion += 1;
  }

  function defaultDeliveryAttacheImportState() {
    return {
      isOpen: false,
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

  function isPdfFile(file) {
    if (!file) {
      return false;
    }
    const name = String(file.name || "").toLowerCase();
    const type = String(file.type || "").toLowerCase();
    return type === "application/pdf" || name.endsWith(".pdf");
  }

  function defaultDeliveryDocketImportStateFallback() {
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

  return {
    openDeliveryAttacheImport,
    closeDeliveryAttacheImport,
    chooseDeliveryImportSource,
    backDeliveryImportToSources,
    updateDeliveryAttacheImportFiles,
    removeDeliveryAttacheImportFile,
    previewDeliveryAttacheImport,
    backDeliveryAttacheImportToFiles,
    updateDeliveryAttacheImportRow,
    updateDeliveryAttacheImportProductLine,
    addDeliveryAttacheImportProductLine,
    removeDeliveryAttacheImportProductLine,
    toggleDeliveryAttacheImportRow,
    toggleDeliveryAttacheImportExpanded,
    selectAllReadyDeliveryAttacheRows,
    clearDeliveryAttacheImportSelection,
    updateDeliveryAttacheReviewSearch,
    updateDeliveryAttacheReviewFilter,
    commitDeliveryAttacheImport,
    hasDeliveryAttacheDraft,
    invalidateDeliveryAttachePreview,
    defaultDeliveryAttacheImportState,
    isPdfFile,
  };
}
