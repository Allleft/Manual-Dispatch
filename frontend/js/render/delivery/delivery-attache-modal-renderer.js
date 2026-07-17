import { createIcon } from "../../utils/icon-utils.js";

import {
  formatOptional,
  formatPluralLoadUnit,
} from "../../utils/format-utils.js";

import {
  createWorkspaceModal,
  createFormSection,
  createInlineInput,
  createInlineTextarea,
  createInlineSelect,
  createActionButton,
  createSectionHeading,
  createBadge,
  createStatus,
  createEmptyState,
} from "./delivery-renderer-utils.js";

export function createDeliveryAttacheImportModal(state, actions) {
  const importState = state.deliveryAttacheImportState || {};
  if (!importState.isOpen) {
    return document.createDocumentFragment();
  }
  const modal = createWorkspaceModal(
    "Import Attache Invoices",
    actions.closeDeliveryAttacheImport,
    {
      eyebrow: "Delivery Order Import",
      subtitle: "Upload PDF invoices, review extracted values, then confirm selected imports.",
      iconName: "cloud-upload",
      width: "import",
    },
  );
  const body = modal.querySelector(".workspace-modal-body");
  if (importState.error) {
    body.append(createStatus(importState.error, "error"));
  }
  if (importState.success) {
    body.append(createStatus(importState.success, "loading"));
  }
  if ((importState.step || "files") === "review") {
    body.append(createDeliveryAttachePreview(importState, actions));
  } else {
    body.append(createDeliveryAttacheFileStep(importState, actions));
  }
  return modal;
}

export function createDeliveryAttacheFileStep(importState, actions) {
  const controls = document.createElement("section");
  controls.className = "workspace-modal-section workspace-attache-file-step";
  controls.append(createSectionHeading("Step 1: Select PDF invoices", "PDF invoices only. Choose one or more Attache invoice PDFs."));
  const dropZone = document.createElement("div");
  dropZone.className = "workspace-attache-dropzone";
  let dragDepth = 0;
  const setDragActive = (active) => {
    dropZone.classList.toggle("workspace-attache-dropzone-active", active);
  };
  dropZone.addEventListener("dragenter", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepth += 1;
    setDragActive(true);
  });
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "copy";
    }
    setDragActive(true);
  });
  dropZone.addEventListener("dragleave", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) {
      setDragActive(false);
    }
  });
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepth = 0;
    setDragActive(false);
    actions.updateDeliveryAttacheImportFiles(event.dataTransfer?.files || [], {
      source: "drop",
    });
  });
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "application/pdf,.pdf";
  fileInput.multiple = true;
  fileInput.className = "visually-hidden-file-input";
  fileInput.id = "delivery-attache-file-input";
  fileInput.addEventListener("change", () => actions.updateDeliveryAttacheImportFiles(fileInput.files));
  const fileButton = document.createElement("label");
  fileButton.className = "button-secondary workspace-action-button workspace-file-select-button";
  fileButton.setAttribute("for", fileInput.id);
  fileButton.append(createIcon("document"), document.createTextNode("Choose PDF files"));
  const selected = document.createElement("strong");
  selected.textContent = `${(importState.files || []).length} file${(importState.files || []).length === 1 ? "" : "s"} selected`;
  const helper = document.createElement("p");
  helper.className = "workspace-muted";
  helper.textContent = "Drop PDF files here, or use Choose PDF files.";
  dropZone.append(fileInput, fileButton, selected, helper);
  const fileList = document.createElement("div");
  fileList.className = "workspace-attache-file-list";
  (importState.files || []).forEach((file, index) => {
    const chip = document.createElement("span");
    chip.className = "workspace-file-chip";
    chip.append(document.createTextNode(file.name || `PDF ${index + 1}`));
    chip.append(createActionButton("Remove", () => actions.removeDeliveryAttacheImportFile(index), {
      disabled: importState.isPreviewing,
      className: "workspace-file-chip-remove",
    }));
    fileList.append(chip);
  });
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer";
  footer.append(
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton("Preview Import", actions.previewDeliveryAttacheImport, {
      iconName: "view",
      primary: true,
      disabled: importState.isPreviewing || !(importState.files || []).length,
    }),
  );
  controls.append(dropZone, fileList, footer);
  return controls;
}

export function createDeliveryAttachePreview(importState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-attache-review-step";
  const rows = importState.rows || [];
  section.append(createSectionHeading("Step 2: Review extracted invoices", "Check parsed values, expand rows for edits, then confirm selected imports."));
  if (!rows.length) {
    section.append(createEmptyState("No invoice previews yet.", "document"));
    return section;
  }
  section.append(createAttacheSummaryStrip(rows));
  const selectionRow = document.createElement("div");
  selectionRow.className = "workspace-action-row workspace-attache-selection-row";
  selectionRow.append(
    createActionButton("Select all ready", actions.selectAllReadyDeliveryAttacheRows),
    createActionButton("Clear selection", actions.clearDeliveryAttacheImportSelection),
  );
  const list = document.createElement("div");
  list.className = "workspace-attache-review-list";
  rows.forEach((row) => {
    list.append(createAttacheReviewRow(row, importState, actions));
  });
  const selectedCount = rows.filter((row) => row.selected && row.importable && !row.is_duplicate).length;
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer workspace-modal-footer-sticky";
  footer.append(
    createActionButton("Back to files", actions.backDeliveryAttacheImportToFiles),
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton(`Confirm Import (${selectedCount} selected)`, actions.commitDeliveryAttacheImport, {
      disabled: importState.isCommitting || selectedCount === 0,
      primary: true,
      iconName: "cloud-upload",
    }),
  );
  section.append(selectionRow, list, footer);
  return section;
}

export function createAttacheSummaryStrip(rows) {
  const ready = rows.filter((row) => row.importable && !row.is_duplicate && !(row.warnings || []).length).length;
  const duplicates = rows.filter((row) => row.is_duplicate).length;
  const warnings = rows.filter((row) => (row.warnings || []).length || !row.importable).length;
  const selected = rows.filter((row) => row.selected && row.importable && !row.is_duplicate).length;
  const strip = document.createElement("div");
  strip.className = "workspace-attache-summary-strip";
  [
    ["Total files", rows.length],
    ["Ready to import", ready],
    ["Duplicates", duplicates],
    ["Warnings / parse issues", warnings],
    ["Selected for import", selected],
  ].forEach(([label, value]) => {
    strip.append(createMetricPill(label, value));
  });
  return strip;
}

export function createAttacheReviewRow(row, importState, actions) {
  const card = document.createElement("article");
  card.className = "workspace-attache-review-card";
  const expanded = Boolean((importState.expandedRowIds || {})[row.row_id]);
  const status = attacheRowStatus(row);
  const header = document.createElement("div");
  header.className = "workspace-attache-review-header";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = Boolean(row.selected);
  checkbox.disabled = importState.isCommitting || row.is_duplicate || !row.importable;
  checkbox.addEventListener("change", () => actions.toggleDeliveryAttacheImportRow(row.row_id, checkbox.checked));
  const summary = document.createElement("div");
  summary.className = "workspace-attache-review-summary";
  summary.append(
    createBadge(status),
    createInlineMeta("Invoice", row.invoice_number),
    createInlineMeta("Order", row.order_no),
    createInlineMeta("Customer", row.company_name),
    createInlineMeta("Delivery Date", row.delivery_date),
    createInlineMeta("Load", `${row.pallet_quantity || 0} pallets / ${row.loose_bags_quantity || 0} bags`),
  );
  const warning = document.createElement("p");
  warning.className = "workspace-attache-warning-summary";
  warning.textContent = row.is_duplicate
    ? "Duplicate invoice already exists and cannot be selected."
    : (row.warnings || []).join("; ");
  const expand = createActionButton(expanded ? "Collapse" : "Expand", () =>
    actions.toggleDeliveryAttacheImportExpanded(row.row_id));
  header.append(checkbox, summary, expand);
  card.append(header);
  if (warning.textContent) {
    card.append(warning);
  }
  if (expanded) {
    card.append(createAttacheExpandedEditor(row, actions));
  }
  return card;
}

export function createAttacheExpandedEditor(row, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-attache-expanded-editor";
  wrapper.append(
    createFormSection("Customer and Invoice", [
      createInlineField("Invoice Number", createInlineInput(row.invoice_number, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "invoice_number", value))),
      createInlineField("Order Number", createInlineInput(row.order_no, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "order_no", value))),
      createInlineField("Company Name", createInlineInput(row.company_name, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "company_name", value))),
      createInlineField("Phone", createInlineInput(row.phone, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "phone", value))),
    ]),
    createFormSection("Delivery Details", [
      createInlineField("Delivery Address", createInlineInput(row.delivery_address, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_address", value))),
      createInlineField("Suburb", createInlineInput(row.suburb, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "suburb", value))),
      createInlineField("Postcode", createInlineInput(row.postcode, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "postcode", value))),
      createInlineField("Delivery Date", createInlineInput(row.delivery_date, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_date", value), "date")),
      createInlineField("Start Time", createInlineInput(row.start_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "start_time", value), "time")),
      createInlineField("End Time", createInlineInput(row.end_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "end_time", value), "time")),
      createInlineField("Urgency", createInlineSelect(row.urgency || "Normal", [
        { value: "Normal", label: "Normal" },
        { value: "Urgent", label: "Urgent" },
      ], (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "urgency", value))),
    ]),
    createFormSection("Load", [
      createInlineField("Pallet Quantity", createInlineInput(row.pallet_quantity, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "pallet_quantity", Number(value || 0)), "number")),
      createInlineField("Loose Bags Quantity", createInlineInput(row.loose_bags_quantity, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "loose_bags_quantity", Number(value || 0)), "number")),
    ]),
    createFormSection("Product Lines", [createAttacheProductLineEditor(row, actions)]),
    createFormSection("Notes", [createInlineField("Notes", createInlineTextarea(row.note, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "note", value)))]),
  );
  return wrapper;
}

export function attacheRowStatus(row) {
  if (!row.importable) {
    return "Not importable";
  }
  if (row.is_duplicate) {
    return "Duplicate";
  }
  if ((row.warnings || []).length) {
    return "Warning";
  }
  return "Ready";
}

export function createInlineMeta(labelText, value) {
  const item = document.createElement("span");
  item.className = "workspace-inline-meta";
  item.textContent = `${labelText}: ${formatOptional(value)}`;
  return item;
}

export function createMetricPill(labelText, value) {
  const pill = document.createElement("span");
  pill.className = "workspace-metric-pill";
  pill.textContent = `${labelText}: ${value}`;
  return pill;
}

export function createInlineField(labelText, control) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  label.append(text, control);
  return label;
}

export function createAttacheProductLineEditor(row, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-attache-products";
  (row.product_lines || []).forEach((line, index) => {
    const lineRow = document.createElement("div");
    lineRow.className = "workspace-attache-product-row";
    lineRow.append(
      createInlineInput(line.product_name, (value) =>
        actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "product_name", value)),
      createInlineInput(line.quantity, (value) =>
        actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "quantity", value), "number"),
      createInlineSelect(line.unit || "PALLETS", [
        { value: "PALLETS", label: "PALLETS" },
        { value: "BAGS", label: "BAGS" },
        { value: "CARTONS", label: "CARTONS" },
      ], (value) =>
        actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "unit", value)),
      createActionButton("Remove", () =>
        actions.removeDeliveryAttacheImportProductLine(row.row_id, index)),
    );
    wrapper.append(lineRow);
  });
  if (!(row.product_lines || []).length) {
    const empty = document.createElement("p");
    empty.className = "workspace-muted";
    empty.textContent = "No product lines parsed.";
    wrapper.append(empty);
  }
  wrapper.append(createActionButton("Add Product Line", () =>
    actions.addDeliveryAttacheImportProductLine(row.row_id)));
  return wrapper;
}

export function productLineSummary(row) {
  return (row.product_lines || [])
    .map((line) => `${formatOptional(line.product_name)} - ${line.quantity} ${formatPluralLoadUnit(line.unit, line.quantity)}`)
    .join("; ") || "No product lines";
}
