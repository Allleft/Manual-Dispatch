import {
  apiCommitAttacheInvoicePdfImport,
  apiPreviewAttacheInvoicePdfImport,
} from "../api/manual-dispatch-api.js";


export function createAttacheInvoiceImportActions({
  loadBoard,
  renderAttacheInvoiceImportModal,
  state,
}) {
  function openImportModal() {
    state.isAttacheInvoiceImportOpen = true;
    state.attacheInvoiceImportFiles = [];
    state.attacheInvoiceImportRows = [];
    state.attacheInvoiceImportError = "";
    state.attacheInvoiceImportSuccess = "";
    renderAttacheInvoiceImportModal();
  }

  function closeImportModal() {
    state.isAttacheInvoiceImportOpen = false;
    state.isAttacheInvoiceImportPreviewing = false;
    state.isAttacheInvoiceImportCommitting = false;
    state.attacheInvoiceImportFiles = [];
    state.attacheInvoiceImportRows = [];
    state.attacheInvoiceImportError = "";
    state.attacheInvoiceImportSuccess = "";
    renderAttacheInvoiceImportModal();
  }

  function updateFiles(files) {
    state.attacheInvoiceImportFiles = Array.from(files || []);
    state.attacheInvoiceImportError = "";
    state.attacheInvoiceImportSuccess = "";
    renderAttacheInvoiceImportModal();
  }

  async function previewImport() {
    if (state.isAttacheInvoiceImportPreviewing || state.attacheInvoiceImportFiles.length === 0) {
      return;
    }

    state.isAttacheInvoiceImportPreviewing = true;
    state.attacheInvoiceImportError = "";
    state.attacheInvoiceImportSuccess = "";
    renderAttacheInvoiceImportModal();

    try {
      const response = await apiPreviewAttacheInvoicePdfImport(state.attacheInvoiceImportFiles);
      state.attacheInvoiceImportRows = (response.rows || []).map((row) => ({
        ...row,
        selected: Boolean(row.selected && row.importable && !row.is_duplicate),
      }));
    } catch (error) {
      state.attacheInvoiceImportError = `Unable to preview Attache invoices. ${error.message}`;
    } finally {
      state.isAttacheInvoiceImportPreviewing = false;
      renderAttacheInvoiceImportModal();
    }
  }

  function updatePreviewRow(rowId, field, value) {
    state.attacheInvoiceImportRows = state.attacheInvoiceImportRows.map((row) =>
      row.row_id === rowId ? { ...row, [field]: value } : row,
    );
  }

  function togglePreviewRow(rowId, selected) {
    state.attacheInvoiceImportRows = state.attacheInvoiceImportRows.map((row) => {
      if (row.row_id !== rowId || row.is_duplicate || !row.importable) {
        return row;
      }
      return { ...row, selected };
    });
    renderAttacheInvoiceImportModal();
  }

  function clearPreviewSelection() {
    state.attacheInvoiceImportRows = state.attacheInvoiceImportRows.map((row) => ({
      ...row,
      selected: false,
    }));
    renderAttacheInvoiceImportModal();
  }

  async function commitImport() {
    if (state.isAttacheInvoiceImportCommitting) {
      return;
    }

    const selectedRows = state.attacheInvoiceImportRows.filter((row) => row.selected);
    if (selectedRows.length === 0) {
      state.attacheInvoiceImportError = "Select at least one non-duplicate invoice to import.";
      renderAttacheInvoiceImportModal();
      return;
    }

    state.isAttacheInvoiceImportCommitting = true;
    state.attacheInvoiceImportError = "";
    state.attacheInvoiceImportSuccess = "";
    renderAttacheInvoiceImportModal();

    try {
      const response = await apiCommitAttacheInvoicePdfImport({
        rows: state.attacheInvoiceImportRows,
      });
      state.attacheInvoiceImportSuccess =
        `Imported ${response.imported_count || 0} Delivery Orders. `
        + `${response.skipped_count || 0} rows skipped.`;
      state.attacheInvoiceImportRows = state.attacheInvoiceImportRows.map((row) =>
        row.selected ? { ...row, selected: false } : row,
      );
      await loadBoard(state.dispatchDate, { force: true });
    } catch (error) {
      state.attacheInvoiceImportError = `Unable to import Attache invoices. ${error.message}`;
    } finally {
      state.isAttacheInvoiceImportCommitting = false;
      renderAttacheInvoiceImportModal();
    }
  }

  return {
    clearPreviewSelection,
    closeImportModal,
    commitImport,
    openImportModal,
    previewImport,
    togglePreviewRow,
    updateFiles,
    updatePreviewRow,
  };
}
