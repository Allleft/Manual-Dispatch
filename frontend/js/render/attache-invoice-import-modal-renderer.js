import { state } from "../state/app-state.js";
import {
  createModalKicker,
  setButtonContent,
} from "../utils/dom-utils.js";
import { createIcon } from "../utils/icon-utils.js";
import { formatOptional } from "../utils/format-utils.js";


const EDITABLE_FIELDS = [
  ["order_no", "text"],
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
  onClearSelection,
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
  backdrop.className = "detail-backdrop attache-import-backdrop";

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
  title.textContent = "Import Attach\u00e9 Invoices";
  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  setButtonContent(closeButton, "Close", "x", { iconAfter: true });
  closeButton.disabled = state.isAttacheInvoiceImportPreviewing || state.isAttacheInvoiceImportCommitting;
  closeButton.addEventListener("click", onClose);
  header.append(titleWrap, closeButton);

  const controls = createUploadControls({ onPreview, onUpdateFiles });

  const status = document.createElement("div");
  status.className = "attache-import-status-stack";
  status.hidden = !state.attacheInvoiceImportError && !state.attacheInvoiceImportSuccess;

  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.attacheInvoiceImportError;
  error.textContent = state.attacheInvoiceImportError;

  const success = document.createElement("p");
  success.className = "board-status";
  success.hidden = !state.attacheInvoiceImportSuccess;
  success.textContent = state.attacheInvoiceImportSuccess;
  status.append(error, success);

  modal.append(
    header,
    controls,
    status,
    createPreviewWorkspace({ onClearSelection, onToggleRow, onUpdateRow }),
    createImportFooter(onCommit),
  );
  backdrop.append(modal);
  root.append(backdrop);
}


function createUploadControls({ onPreview, onUpdateFiles }) {
  const controls = document.createElement("section");
  controls.className = "attache-import-controls";

  const controlRow = document.createElement("div");
  controlRow.className = "attache-import-control-row";
  const fileInput = document.createElement("input");
  fileInput.id = "attache-invoice-file-input";
  fileInput.className = "visually-hidden-file-input";
  fileInput.type = "file";
  fileInput.accept = "application/pdf,.pdf";
  fileInput.multiple = true;
  fileInput.disabled = state.isAttacheInvoiceImportPreviewing || state.isAttacheInvoiceImportCommitting;
  fileInput.addEventListener("change", () => onUpdateFiles(fileInput.files));

  const fileSelectButton = document.createElement("label");
  fileSelectButton.className = "button-secondary attache-file-select-button";
  fileSelectButton.setAttribute("for", fileInput.id);
  fileSelectButton.append(createIcon("document"), document.createTextNode("Choose PDF files"));
  if (fileInput.disabled) {
    fileSelectButton.classList.add("is-disabled");
    fileSelectButton.setAttribute("aria-disabled", "true");
    fileSelectButton.addEventListener("click", (event) => event.preventDefault());
  }

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
  controlRow.append(fileSelectButton, fileInput, selectedFiles, previewButton);

  const helper = document.createElement("p");
  helper.className = "attache-import-helper";
  helper.append(
    createIcon("info"),
    document.createTextNode(
      "Upload text-based Attach\u00e9 invoice PDFs, review parsed delivery orders, edit fields, then confirm import.",
    ),
  );
  controls.append(controlRow, helper);
  return controls;
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


function createPreviewWorkspace({ onClearSelection, onToggleRow, onUpdateRow }) {
  const wrapper = document.createElement("section");
  wrapper.className = "attache-import-preview";

  if (state.attacheInvoiceImportRows.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-board attache-import-empty";
    empty.append(
      createIcon("document"),
      document.createTextNode("No invoice previews yet. Choose PDF files, then preview the import."),
    );
    wrapper.append(empty);
    return wrapper;
  }

  const workspace = document.createElement("div");
  workspace.className = "attache-import-workspace";
  const tableScroll = document.createElement("div");
  tableScroll.className = "attache-import-table-wrap attache-import-preview-table-wrap";
  const table = document.createElement("table");
  table.className = "spec-table attache-import-table";
  table.append(createTableHead());

  const tbody = document.createElement("tbody");
  state.attacheInvoiceImportRows.forEach((row) => {
    tbody.append(createPreviewRow(row, { onToggleRow, onUpdateRow }));
  });
  table.append(tbody);
  tableScroll.append(table);

  const selectedCount = state.attacheInvoiceImportRows.filter((row) => row.selected).length;
  const importableCount = state.attacheInvoiceImportRows.filter(
    (row) => row.importable && !row.is_duplicate,
  ).length;
  const selectionFooter = document.createElement("div");
  selectionFooter.className = "attache-import-selection-footer";

  const selectionSummary = document.createElement("span");
  selectionSummary.className = "attache-import-selection-summary";
  selectionSummary.textContent = `${selectedCount} of ${importableCount} rows selected`;

  const clearSelection = document.createElement("button");
  clearSelection.type = "button";
  clearSelection.className = "button-link attache-import-clear-selection";
  clearSelection.textContent = "Clear selection";
  clearSelection.disabled = state.isAttacheInvoiceImportCommitting || selectedCount === 0;
  clearSelection.addEventListener("click", onClearSelection);
  selectionFooter.append(selectionSummary, clearSelection);

  if (importableCount === 0) {
    const noImportableRows = document.createElement("p");
    noImportableRows.className = "attache-import-no-importable";
    noImportableRows.textContent = "No importable invoice rows are available.";
    selectionFooter.append(noImportableRows);
  }

  workspace.append(tableScroll, selectionFooter);
  wrapper.append(workspace);
  return wrapper;
}


function createImportFooter(onCommit) {
  const footer = document.createElement("footer");
  footer.className = "attache-import-footer";
  const selectedCount = state.attacheInvoiceImportRows.filter((row) => row.selected).length;
  const commitButton = document.createElement("button");
  commitButton.type = "button";
  commitButton.className = "attache-import-confirm-button";
  setButtonContent(
    commitButton,
    state.isAttacheInvoiceImportCommitting ? "Importing..." : "Confirm Import",
    "cloud-upload",
  );
  commitButton.disabled = state.isAttacheInvoiceImportCommitting || selectedCount === 0;
  commitButton.addEventListener("click", onCommit);
  footer.append(commitButton);
  return footer;
}


function createTableHead() {
  const labels = [
    "Import",
    "Invoice #",
    "Order #",
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
  tr.classList.toggle("attache-import-row-selected", Boolean(row.selected));
  tr.classList.toggle("attache-import-row-warning", Boolean(row.warnings?.length));
  tr.classList.toggle("attache-import-row-unavailable", !row.importable || row.is_duplicate);

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = Boolean(row.selected);
  checkbox.disabled = state.isAttacheInvoiceImportCommitting || !row.importable || row.is_duplicate;
  checkbox.addEventListener("change", () => onToggleRow(row.row_id, checkbox.checked));
  tr.append(createCell(checkbox));

  tr.append(createReadOnlyCell(row.invoice_number, "attache-import-invoice-number"));
  tr.append(createCell(createInput(row, "order_no", "text", onUpdateRow)));
  tr.append(createReadOnlyCell(row.company_name, "attache-import-customer"));
  EDITABLE_FIELDS.forEach(([field, type]) => {
    if (["phone", "delivery_address", "suburb", "postcode", "delivery_date", "start_time", "end_time", "pallet_quantity", "loose_bags_quantity"].includes(field)) {
      tr.append(createCell(createInput(row, field, type, onUpdateRow)));
    }
  });
  tr.append(createCell(createProductLinesCard(row.product_lines)));
  tr.append(createCell(createInput(row, "note", "textarea", onUpdateRow)));
  tr.append(createCell(createWarningsCard(row.warnings)));
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
  input.className = `attache-import-input attache-import-input-${field.replaceAll("_", "-")}`;
  input.setAttribute("aria-label", getEditableFieldLabel(field));
  input.disabled = state.isAttacheInvoiceImportCommitting;
  input.addEventListener("input", () => {
    onUpdateRow(row.row_id, field, input.value);
  });
  return input;
}


function createReadOnlyCell(value, className = "") {
  const text = document.createElement("span");
  text.className = className;
  text.textContent = formatOptional(value, "");
  return createCell(text);
}


function createCell(content) {
  const td = document.createElement("td");
  td.append(content);
  return td;
}


function createProductLinesCard(productLines) {
  const card = document.createElement("div");
  card.className = "attache-import-products-card";
  const lines = productLines || [];
  if (lines.length === 0) {
    card.textContent = "No product details";
    card.classList.add("is-empty");
    return card;
  }
  lines.forEach((line) => {
    const item = document.createElement("p");
    const productName = String(line.product_name || "").trim();
    const quantity = String(line.quantity ?? "").trim();
    const unit = formatProductUnit(line.unit, line.quantity);
    item.textContent = `${productName} \u2014 ${quantity} ${unit}`.trim();
    card.append(item);
  });
  return card;
}


function createWarningsCard(warnings) {
  const card = document.createElement("div");
  const warningList = warnings || [];
  card.className = `attache-import-warnings-card${warningList.length ? " has-warnings" : " is-empty"}`;
  if (warningList.length === 0) {
    card.textContent = "No warnings";
    return card;
  }
  warningList.forEach((warning) => {
    const item = document.createElement("p");
    item.textContent = warning;
    card.append(item);
  });
  return card;
}


function formatProductUnit(unit, quantity) {
  const normalized = String(unit || "").trim().toUpperCase();
  const singular = Number(quantity) === 1;
  if (normalized === "PALLETS") {
    return singular ? "Pallet" : "Pallets";
  }
  if (normalized === "BAGS") {
    return singular ? "Bag" : "Bags";
  }
  if (normalized === "CARTONS") {
    return singular ? "Carton" : "Cartons";
  }
  return unit || "";
}


function getEditableFieldLabel(field) {
  return {
    delivery_address: "Address",
    delivery_date: "Delivery Date",
    end_time: "End",
    loose_bags_quantity: "Loose Bags",
    note: "Notes",
    order_no: "Order Number",
    pallet_quantity: "Pallets",
    phone: "Phone",
    postcode: "Postcode",
    start_time: "Start",
    suburb: "Suburb",
  }[field] || field;
}
