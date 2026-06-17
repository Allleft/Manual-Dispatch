import { state } from "../state/app-state.js";
import {
  createModalKicker,
  setButtonContent,
} from "../utils/dom-utils.js";
import { formatOptional } from "../utils/format-utils.js";


const EDITABLE_FIELDS = [
  ["phone", "text"],
  ["delivery_address", "text"],
  ["suburb", "text"],
  ["postcode", "text"],
  ["delivery_date", "date"],
  ["start_time", "time"],
  ["end_time", "time"],
  ["pallet_quantity", "number"],
  ["loose_bags_quantity", "number"],
  ["note", "textarea"],
];


export function renderAttacheInvoiceImportModal({
  onClose,
  onCommit,
  onPreview,
  onToggleRow,
  onUpdateFiles,
  onUpdateRow,
}) {
  let root = document.querySelector("#attache-invoice-import-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "attache-invoice-import-root";
    document.body.append(root);
  }

  root.innerHTML = "";
  if (!state.isAttacheInvoiceImportOpen) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop";

  const modal = document.createElement("article");
  modal.className = "order-detail-modal attache-import-modal modal-shell modal-accent-blue";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "attache-import-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const header = document.createElement("div");
  header.className = "detail-header";
  const titleWrap = document.createElement("div");
  const kicker = createModalKicker("Delivery Order import", "cloud-upload");
  const title = document.createElement("h2");
  title.id = "attache-import-title";
  title.textContent = "Import Attache Invoices";
  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  setButtonContent(closeButton, "Close", "x", { iconAfter: true });
  closeButton.disabled = state.isAttacheInvoiceImportPreviewing || state.isAttacheInvoiceImportCommitting;
  closeButton.addEventListener("click", onClose);
  header.append(titleWrap, closeButton);

  const intro = document.createElement("p");
  intro.className = "compact-note";
  intro.textContent =
    "Upload text-based Attache invoice PDFs, preview parsed Delivery Orders, edit fields, then confirm import.";

  const controls = document.createElement("div");
  controls.className = "attache-import-controls";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "application/pdf,.pdf";
  fileInput.multiple = true;
  fileInput.disabled = state.isAttacheInvoiceImportPreviewing || state.isAttacheInvoiceImportCommitting;
  fileInput.addEventListener("change", () => onUpdateFiles(fileInput.files));

  const selectedFiles = createSelectedFileFeedback();

  const previewButton = document.createElement("button");
  previewButton.type = "button";
  setButtonContent(
    previewButton,
    state.isAttacheInvoiceImportPreviewing ? "Previewing..." : "Preview Import",
    "eye",
  );
  previewButton.disabled =
    state.isAttacheInvoiceImportPreviewing
    || state.isAttacheInvoiceImportCommitting
    || state.attacheInvoiceImportFiles.length === 0;
  previewButton.addEventListener("click", onPreview);
  controls.append(fileInput, selectedFiles, previewButton);

  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.attacheInvoiceImportError;
  error.textContent = state.attacheInvoiceImportError;

  const success = document.createElement("p");
  success.className = "board-status";
  success.hidden = !state.attacheInvoiceImportSuccess;
  success.textContent = state.attacheInvoiceImportSuccess;

  modal.append(header, intro, controls, error, success, createPreviewTable({
    onCommit,
    onToggleRow,
    onUpdateRow,
  }));
  backdrop.append(modal);
  root.append(backdrop);
}


function createSelectedFileFeedback() {
  const selectedFiles = state.attacheInvoiceImportFiles || [];
  const feedback = document.createElement("p");
  feedback.className = "compact-note";
  feedback.setAttribute("aria-live", "polite");
  if (selectedFiles.length === 0) {
    feedback.textContent = "No PDF files selected.";
    return feedback;
  }
  if (selectedFiles.length === 1) {
    feedback.textContent = `1 file selected: ${selectedFiles[0].name}`;
    return feedback;
  }
  feedback.textContent = `${selectedFiles.length} files selected`;
  return feedback;
}


function createPreviewTable({ onCommit, onToggleRow, onUpdateRow }) {
  const wrapper = document.createElement("div");
  wrapper.className = "attache-import-preview";

  if (state.attacheInvoiceImportRows.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-board";
    empty.textContent = "No invoice previews yet.";
    wrapper.append(empty);
    return wrapper;
  }

  const tableWrap = document.createElement("div");
  tableWrap.className = "attache-import-table-wrap";
  const table = document.createElement("table");
  table.className = "spec-table attache-import-table";
  table.append(createTableHead());

  const tbody = document.createElement("tbody");
  state.attacheInvoiceImportRows.forEach((row) => {
    tbody.append(createPreviewRow(row, { onToggleRow, onUpdateRow }));
  });
  table.append(tbody);
  tableWrap.append(table);

  const selectedCount = state.attacheInvoiceImportRows.filter((row) => row.selected).length;
  const actions = document.createElement("div");
  actions.className = "form-actions";
  const commitButton = document.createElement("button");
  commitButton.type = "button";
  setButtonContent(
    commitButton,
    state.isAttacheInvoiceImportCommitting ? "Importing..." : "Confirm Import",
    "cloud-upload",
  );
  commitButton.disabled = state.isAttacheInvoiceImportCommitting || selectedCount === 0;
  commitButton.addEventListener("click", onCommit);
  actions.append(commitButton);

  wrapper.append(tableWrap, actions);
  return wrapper;
}


function createTableHead() {
  const labels = [
    "Import",
    "Invoice No",
    "Customer",
    "Phone",
    "Address",
    "Suburb",
    "Postcode",
    "Delivery Date",
    "Start",
    "End",
    "Pallets",
    "Loose Bags",
    "Products",
    "Notes",
    "Warnings",
  ];
  const thead = document.createElement("thead");
  const tr = document.createElement("tr");
  labels.forEach((label) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    tr.append(th);
  });
  thead.append(tr);
  return thead;
}


function createPreviewRow(row, { onToggleRow, onUpdateRow }) {
  const tr = document.createElement("tr");
  tr.classList.toggle("attache-import-row-warning", Boolean(row.warnings?.length));

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = Boolean(row.selected);
  checkbox.disabled = state.isAttacheInvoiceImportCommitting || !row.importable || row.is_duplicate;
  checkbox.addEventListener("change", () => onToggleRow(row.row_id, checkbox.checked));
  tr.append(createCell(checkbox));

  tr.append(createReadOnlyCell(row.invoice_number));
  tr.append(createReadOnlyCell(row.company_name));
  EDITABLE_FIELDS.forEach(([field, type]) => {
    if (["phone", "delivery_address", "suburb", "postcode", "delivery_date", "start_time", "end_time", "pallet_quantity", "loose_bags_quantity"].includes(field)) {
      tr.append(createCell(createInput(row, field, type, onUpdateRow)));
    }
  });
  tr.append(createReadOnlyCell(formatProductLines(row.product_lines)));
  tr.append(createCell(createInput(row, "note", "textarea", onUpdateRow)));
  tr.append(createReadOnlyCell((row.warnings || []).join("; ")));
  return tr;
}


function createInput(row, field, type, onUpdateRow) {
  const input = type === "textarea"
    ? document.createElement("textarea")
    : document.createElement("input");
  if (type !== "textarea") {
    input.type = type;
  }
  if (type === "number") {
    input.min = "0";
  }
  input.value = row[field] ?? "";
  input.disabled = state.isAttacheInvoiceImportCommitting;
  input.addEventListener("input", () => {
    onUpdateRow(row.row_id, field, input.value);
  });
  return input;
}


function createReadOnlyCell(value) {
  return createCell(document.createTextNode(formatOptional(value, "")));
}


function createCell(content) {
  const td = document.createElement("td");
  td.append(content);
  return td;
}


function formatProductLines(productLines) {
  return (productLines || [])
    .map((line) => `${line.product_name || ""} - ${line.quantity || ""} ${line.unit || ""}`.trim())
    .filter(Boolean)
    .join("; ");
}
