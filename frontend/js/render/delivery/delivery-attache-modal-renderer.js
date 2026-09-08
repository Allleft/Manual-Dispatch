import { createIcon } from "../../utils/icon-utils.js";

import {
  formatProductDetailLine,
  formatOptional,
} from "../../utils/format-utils.js";
import {
  formatDeliveryAreaLabel,
  formatDeliveryRegionLabel,
} from "../../utils/delivery-area-utils.js";

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
import { formatProductLineTotals } from "./delivery-order-modal-renderer.js";

export function createDeliveryAttacheImportModal(state, actions) {
  const importState = state.deliveryAttacheImportState || {};
  if (!importState.isOpen) {
    return document.createDocumentFragment();
  }
  const source = state.deliveryDocumentImportState?.source || "attache";
  if (source === "chooser") {
    const chooser = createWorkspaceModal(
      "Import Delivery Document",
      actions.closeDeliveryAttacheImport,
      {
        eyebrow: "Delivery Order Import",
        subtitle: "Choose the document source to start the matching review workflow.",
        iconName: "cloud-upload",
        width: "import",
      },
    );
    chooser.querySelector(".workspace-modal-body").append(
      createDeliveryImportSourceChooser(actions),
    );
    return chooser;
  }
  if (source === "docket") {
    return createDeliveryDocketImportModal(
      state.deliveryDocketImportState || {},
      actions,
    );
  }
  if (source === "attache-direct") {
    return createDeliveryDirectAttacheImportModal(importState, actions);
  }
  if (source === "attache-current-future") {
    return createDeliveryAttacheCurrentFutureImportModal(
      state.deliveryAttacheCurrentFutureImportState || {},
      actions,
    );
  }
  const modal = createWorkspaceModal(
    "Import Attaché Invoices",
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
  if (
    (importState.step || "files") === "review"
    && (importState.reviewSource || "attache") === "attache"
  ) {
    body.append(createDeliveryAttachePreview(importState, actions));
  } else {
    body.append(createDeliveryAttacheFileStep(importState, actions));
  }
  return modal;
}

export function createDeliveryImportSourceChooser(actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-import-source-step";
  section.append(createSectionHeading(
    "Select document source",
    "Each source keeps its own draft and uses the matching review workflow.",
  ));
  const choices = document.createElement("div");
  choices.className = "workspace-import-source-grid";
  choices.append(
    createImportSourceChoice(
      "Import Attaché PDF",
      "Upload one or more Attaché PDF invoices.",
      "document",
      () => actions.chooseDeliveryImportSource("attache"),
    ),
    createImportSourceChoice(
      "Import Delivery Docket",
      "Import Delivery Docket DOCX files.",
      "cloud-upload",
      () => actions.chooseDeliveryImportSource("docket"),
    ),
    createImportSourceChoice(
      "Import from Attaché",
      "Find one invoice through the read-only Attaché bridge.",
      "view",
      () => actions.chooseDeliveryImportSource("attache-direct"),
    ),
    createImportSourceChoice(
      "Import Today & Future Invoices",
      "Load Attaché customer invoices dated today or later.",
      "calendar",
      () => actions.chooseDeliveryImportSource("attache-current-future"),
    ),
  );
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer";
  footer.append(createActionButton("Cancel", actions.closeDeliveryAttacheImport));
  section.append(choices, footer);
  return section;
}

function createImportSourceChoice(titleText, description, iconName, onSelect) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "workspace-import-source-card";
  const icon = document.createElement("span");
  icon.className = "workspace-import-source-icon";
  icon.append(createIcon(iconName));
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = titleText;
  const detail = document.createElement("span");
  detail.textContent = description;
  copy.append(title, detail);
  button.append(icon, copy);
  button.addEventListener("click", onSelect);
  return button;
}

export function createDeliveryDirectAttacheImportModal(importState, actions) {
  const modal = createWorkspaceModal(
    "Import from Attaché",
    actions.closeDeliveryAttacheImport,
    {
      eyebrow: "Delivery Order Import",
      subtitle: "Find an invoice, review the returned values, then confirm the import.",
      iconName: "view",
      width: "import",
    },
  );
  const body = modal.querySelector(".workspace-modal-body");
  const hasDirectResult = (
    (importState.step || "files") === "review"
    && importState.reviewSource === "attache-direct"
    && (importState.rows || []).length > 0
  );
  body.append(createDeliveryDirectAttacheLookupStep(importState, actions));
  if (importState.error) {
    body.append(createStatus(importState.error, "error"));
  }
  if (importState.success) {
    body.append(createStatus(importState.success, "loading"));
  }
  if (hasDirectResult) {
    body.append(createDeliveryAttachePreview(importState, actions, {
      showFooter: false,
      headingTitle: "Invoice review",
      headingSubtitle: "Review the returned values, expand the invoice for edits, then confirm the import.",
    }));
  }
  body.append(createDeliveryDirectAttacheFooter(importState, actions, hasDirectResult));
  return modal;
}

export function createDeliveryDirectAttacheLookupStep(importState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-attache-direct-step";
  section.append(createSectionHeading(
    "Find Attaché invoice",
    "Enter the invoice number exactly as shown in Attaché.",
  ));

  const lookupRow = document.createElement("div");
  lookupRow.className = "workspace-attache-direct-lookup";
  const field = document.createElement("label");
  field.className = "workspace-field workspace-attache-direct-field";
  const fieldLabel = document.createElement("span");
  fieldLabel.textContent = "Invoice Number";
  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = "numeric";
  input.pattern = "[0-9]*";
  input.autocomplete = "off";
  input.placeholder = "e.g. 123456";
  input.value = importState.directInvoiceNumber || "";
  input.disabled = Boolean(importState.isDirectLookupPending);
  input.addEventListener("input", () => {
    actions.updateDeliveryDirectAttacheInvoiceNumber(input.value);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !importState.isDirectLookupPending) {
      event.preventDefault();
      actions.lookupDeliveryDirectAttacheInvoice();
    }
  });
  field.append(fieldLabel, input);
  const lookupButton = createActionButton(
    importState.isDirectLookupPending ? "Looking up invoice..." : "Find Invoice",
    actions.lookupDeliveryDirectAttacheInvoice,
    {
      primary: true,
      iconName: "view",
      disabled: Boolean(importState.isDirectLookupPending),
    },
  );
  lookupRow.append(field, lookupButton);
  section.append(lookupRow);

  if (importState.isDirectLookupPending) {
    section.append(createStatus("Looking up invoice...", "loading"));
  }
  if (importState.directLookupError) {
    section.append(createStatus(importState.directLookupError, "error"));
  }
  const fallback = document.createElement("p");
  fallback.className = "workspace-muted";
  fallback.textContent = "If lookup is unavailable, go back and use Import Attaché PDF.";

  section.append(fallback);
  return section;
}

function createDeliveryDirectAttacheFooter(importState, actions, hasDirectResult) {
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer workspace-modal-footer-sticky";
  footer.append(
    createActionButton("Back", actions.backDeliveryImportToSources),
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
  );
  if (hasDirectResult) {
    const selectedCount = countSelectedAttacheRows(importState.rows);
    footer.append(createActionButton(
      `Confirm Import (${selectedCount} selected)`,
      actions.commitDeliveryAttacheImport,
      {
        disabled: importState.isCommitting || selectedCount === 0,
        primary: true,
        iconName: "cloud-upload",
      },
    ));
  }
  return footer;
}

export function createDeliveryAttacheCurrentFutureImportModal(importState, actions) {
  const modal = createWorkspaceModal(
    "Import Today & Future Invoices",
    actions.closeDeliveryAttacheImport,
    {
      eyebrow: "Delivery Order Import",
      subtitle: "Load Attaché customer invoices dated today or later. Dates use the Melbourne business date.",
      iconName: "calendar",
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
  if (importState.isLoading) {
    body.append(createStatus("Loading Today & Future Invoices...", "loading"));
  }
  body.append(
    importState.hasLoaded
      ? createDeliveryAttacheCurrentFutureReview(importState, actions)
      : createDeliveryAttacheCurrentFutureLoadStep(importState, actions),
  );
  return modal;
}

function createDeliveryAttacheCurrentFutureLoadStep(importState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-attache-current-future-step";
  section.append(createSectionHeading(
    "Load Today & Future Attaché invoices",
    "Nothing is loaded until you choose Load Today & Future Invoices.",
  ));
  const safety = document.createElement("p");
  safety.className = "workspace-muted";
  safety.textContent = "Attaché access is read-only.";
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer workspace-modal-footer-sticky";
  footer.append(
    createActionButton("Back", actions.backDeliveryImportToSources),
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton(
      importState.isLoading
        ? "Loading Today & Future Invoices..."
        : "Load Today & Future Invoices",
      actions.loadDeliveryAttacheCurrentFutureInvoices,
      {
        primary: true,
        iconName: "view",
        disabled: Boolean(importState.isLoading || importState.isCommitting),
      },
    ),
  );
  section.append(safety, footer);
  return section;
}

function createDeliveryAttacheCurrentFutureReview(importState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-attache-current-future-step";
  const header = document.createElement("div");
  header.className = "workspace-attache-current-future-header";
  header.append(
    createSectionHeading(
      "Today & Future Attaché Invoices",
      `From ${formatCurrentFutureFromDate(importState.fromDate)}`,
    ),
    createActionButton("Refresh", actions.refreshDeliveryAttacheCurrentFutureInvoices, {
      iconName: "refresh",
      disabled: Boolean(importState.isLoading || importState.isCommitting),
    }),
  );
  const rows = importState.rows || [];
  section.append(header, createCurrentFutureSummaryStrip(rows));
  if (rows.length) {
    section.append(createDeliveryAttachePreview(
      importState,
      currentFutureActionAdapter(actions),
      {
        showFooter: false,
        showSummary: false,
        headingTitle: "Invoice review",
        headingSubtitle: "Review the returned values, expand invoices for edits, then confirm selected imports.",
      },
    ));
  } else {
    section.append(createEmptyState(
      "No Attaché invoices dated today or later were found.",
      "document",
    ));
  }
  const selectedCount = countSelectedAttacheRows(rows);
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer workspace-modal-footer-sticky";
  footer.append(
    createActionButton("Back", actions.backDeliveryImportToSources),
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton(
      `Confirm Import (${selectedCount} selected)`,
      actions.commitDeliveryAttacheCurrentFutureImport,
      {
        primary: true,
        iconName: "cloud-upload",
        disabled: Boolean(
          importState.isLoading
          || importState.isCommitting
          || selectedCount === 0,
        ),
      },
    ),
  );
  section.append(footer);
  return section;
}

function createCurrentFutureSummaryStrip(rows) {
  const ready = rows.filter(
    (row) => row.importable
      && !row.is_duplicate
      && !(row.warnings || []).length
      && ["NOT_REQUIRED", "PAID_IN_FULL"].includes(row.payment_eligibility),
  ).length;
  const duplicates = rows.filter((row) => row.is_duplicate).length;
  const paymentRequired = rows.filter(
    (row) => !row.is_duplicate && row.payment_eligibility === "PAYMENT_REQUIRED",
  ).length;
  const needsReview = rows.filter(
    (row) => !row.is_duplicate
      && row.payment_eligibility !== "PAYMENT_REQUIRED"
      && (!row.importable || (row.warnings || []).length),
  ).length;
  const strip = document.createElement("div");
  strip.className = "workspace-attache-summary-strip workspace-attache-current-future-summary";
  [
    ["Found", rows.length],
    ["Ready", ready],
    ["Duplicate", duplicates],
    ["Payment Required", paymentRequired],
    ["Needs Review", needsReview],
  ].forEach(([label, value]) => strip.append(createMetricPill(label, value)));
  return strip;
}

function currentFutureActionAdapter(actions) {
  return {
    updateDeliveryAttacheImportRow:
      actions.updateDeliveryAttacheCurrentFutureImportRow,
    classifyDeliveryAttacheImportRow:
      actions.classifyDeliveryAttacheCurrentFutureRow,
    updateDeliveryAttacheImportProductLine:
      actions.updateDeliveryAttacheCurrentFutureProductLine,
    addDeliveryAttacheImportProductLine:
      actions.addDeliveryAttacheCurrentFutureProductLine,
    removeDeliveryAttacheImportProductLine:
      actions.removeDeliveryAttacheCurrentFutureProductLine,
    toggleDeliveryAttacheImportRow:
      actions.toggleDeliveryAttacheCurrentFutureRow,
    toggleDeliveryAttacheImportExpanded:
      actions.toggleDeliveryAttacheCurrentFutureExpanded,
    selectAllReadyDeliveryAttacheRows:
      actions.selectAllReadyDeliveryAttacheCurrentFutureRows,
    clearDeliveryAttacheImportSelection:
      actions.clearDeliveryAttacheCurrentFutureSelection,
    updateDeliveryAttacheReviewSearch:
      actions.updateDeliveryAttacheCurrentFutureSearch,
    updateDeliveryAttacheReviewFilter:
      actions.updateDeliveryAttacheCurrentFutureFilter,
  };
}

function formatCurrentFutureFromDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  return match ? `${match[3]}/${match[2]}/${match[1]}` : "—";
}

export function createDeliveryDocketImportModal(importState, actions) {
  const modal = createWorkspaceModal(
    "Import Delivery Dockets",
    actions.closeDeliveryAttacheImport,
    {
      eyebrow: "Delivery Order Import",
      subtitle: "Upload DOCX dockets, review extracted values, then confirm selected imports.",
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
  body.append(
    (importState.step || "files") === "review"
      ? createDeliveryDocketPreview(importState, actions)
      : createDeliveryDocketFileStep(importState, actions),
  );
  return modal;
}

export function createDeliveryDocketFileStep(importState, actions) {
  const controls = document.createElement("section");
  controls.className = "workspace-modal-section workspace-attache-file-step workspace-docket-file-step";
  controls.append(createSectionHeading(
    "Step 1: Select Delivery Dockets",
    "DOCX files only. Choose one or more Delivery Docket documents.",
  ));
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
    actions.updateDeliveryDocketImportFiles(event.dataTransfer?.files || [], {
      source: "drop",
    });
  });
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx";
  fileInput.multiple = true;
  fileInput.className = "visually-hidden-file-input";
  fileInput.id = "delivery-docket-file-input";
  fileInput.addEventListener("change", () =>
    actions.updateDeliveryDocketImportFiles(fileInput.files));
  const fileButton = document.createElement("label");
  fileButton.className = "button-secondary workspace-action-button workspace-file-select-button";
  fileButton.setAttribute("for", fileInput.id);
  fileButton.append(createIcon("document"), document.createTextNode("Choose DOCX files"));
  const selected = document.createElement("strong");
  selected.textContent = `${(importState.files || []).length} file${(importState.files || []).length === 1 ? "" : "s"} selected`;
  const helper = document.createElement("p");
  helper.className = "workspace-muted";
  helper.textContent = "Drop DOCX files here, or use Choose DOCX files.";
  dropZone.append(fileInput, fileButton, selected, helper);
  const fileList = document.createElement("div");
  fileList.className = "workspace-attache-file-list";
  (importState.files || []).forEach((file, index) => {
    const chip = document.createElement("span");
    chip.className = "workspace-file-chip";
    chip.append(document.createTextNode(file.name || `DOCX ${index + 1}`));
    chip.append(createActionButton(
      "Remove",
      () => actions.removeDeliveryDocketImportFile(index),
      {
        disabled: importState.isPreviewing,
        className: "workspace-file-chip-remove",
      },
    ));
    fileList.append(chip);
  });
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer";
  footer.append(
    createActionButton("Back", actions.backDeliveryImportToSources),
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton("Preview Import", actions.previewDeliveryDocketImport, {
      iconName: "view",
      primary: true,
      disabled: importState.isPreviewing || !(importState.files || []).length,
    }),
  );
  controls.append(dropZone, fileList, footer);
  return controls;
}

export function createDeliveryDocketPreview(importState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-attache-review-step workspace-docket-review-step";
  const rows = importState.rows || [];
  section.append(createSectionHeading(
    "Step 2: Review extracted Delivery Dockets",
    "Check parsed values, expand rows for edits, then confirm selected imports.",
  ));
  if (!rows.length) {
    section.append(createEmptyState("No Delivery Docket previews yet.", "document"));
    return section;
  }
  section.append(createAttacheSummaryStrip(rows));
  const toolbar = createDeliveryDocketReviewToolbar(importState, actions);
  const list = document.createElement("div");
  list.className = "workspace-attache-review-list workspace-docket-review-list";
  rows.forEach((row) => {
    list.append(createDeliveryDocketReviewRow(row, importState, actions));
  });
  applyAttacheReviewVisibility(list, importState.search, importState.filter);
  const selectedCount = rows.filter(
    (row) => row.selected && row.importable && !row.is_duplicate,
  ).length;
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer workspace-modal-footer-sticky";
  footer.append(
    createActionButton("Back to files", actions.backDeliveryDocketImportToFiles),
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton(
      `Confirm Import (${selectedCount} selected)`,
      actions.commitDeliveryDocketImport,
      {
        disabled: importState.isCommitting || selectedCount === 0,
        primary: true,
        iconName: "cloud-upload",
      },
    ),
  );
  section.append(toolbar, list, footer);
  return section;
}

export function createDeliveryDocketReviewRow(row, importState, actions) {
  const card = document.createElement("article");
  card.className = "workspace-attache-review-card workspace-docket-review-card";
  card.dataset.invoiceReviewId = row.row_id;
  card.dataset.docketReviewId = row.row_id;
  card.dataset.invoiceSearch = [
    row.docket_number,
    row.docket_reference,
    row.invoice_number,
    row.order_no,
    row.company_name,
    row.suburb,
    row.note,
  ].map((value) => String(value || "").toLowerCase()).join(" ");
  card.dataset.invoiceStatus = attacheRowStatus(row).toUpperCase().replaceAll(" ", "_");
  card.dataset.invoiceSelected = row.selected ? "true" : "false";
  const expanded = Boolean((importState.expandedRowIds || {})[row.row_id]);
  const status = attacheRowStatus(row);
  const header = document.createElement("div");
  header.className = "workspace-attache-review-header";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = Boolean(row.selected);
  checkbox.disabled = importState.isCommitting || row.is_duplicate || !row.importable;
  checkbox.setAttribute(
    "aria-label",
    `Select Delivery Docket ${formatOptional(row.docket_number, row.row_id)}`,
  );
  checkbox.addEventListener("change", () =>
    actions.toggleDeliveryDocketImportRow(row.row_id, checkbox.checked));
  const summary = document.createElement("div");
  summary.className = "workspace-attache-review-summary";
  summary.append(
    createBadge(status),
    createInlineMeta("Docket", row.docket_number),
    createInlineMeta("Invoice", row.invoice_number),
    createInlineMeta("Invoice Date", row.invoice_date),
    createInlineMeta("Order", row.order_no),
    createInlineMeta("Customer", row.company_name),
    createInlineMeta("Suburb", row.suburb),
    createInlineMeta("Delivery Area", formatDeliveryAreaLabel(row.delivery_area)),
    createInlineMeta("Region", formatDeliveryRegionLabel(row.auto_delivery_region)),
    createInlineMeta("Delivery Date", row.delivery_date),
    createInlineMeta(
      "Load",
      (row.pallet_quantity || 0) + " pallets / "
        + (row.loose_bags_quantity || 0) + " bags / "
        + (row.carton_quantity || 0) + " cartons",
    ),
  );
  const warning = document.createElement("p");
  warning.className = "workspace-attache-warning-summary";
  warning.textContent = row.is_duplicate
    ? "Duplicate invoice already exists and cannot be selected."
    : (row.warnings || []).join("; ");
  const expand = createActionButton(expanded ? "Collapse" : "Expand", () => {
    const scrollBody = card.closest(".workspace-modal-body");
    const scrollTop = scrollBody?.scrollTop || 0;
    const nextImportState = actions.toggleDeliveryDocketImportExpanded(row.row_id);
    const currentRow = (nextImportState?.rows || []).find(
      (candidate) => candidate.row_id === row.row_id,
    ) || row;
    const replacement = createDeliveryDocketReviewRow(
      currentRow,
      nextImportState || importState,
      actions,
    );
    card.replaceWith(replacement);
    replacement.querySelector("button")?.focus({ preventScroll: true });
    if (scrollBody) {
      scrollBody.scrollTop = scrollTop;
    }
  });
  expand.setAttribute("aria-expanded", String(expanded));
  header.append(checkbox, summary, expand);
  card.append(header);
  if (warning.textContent) {
    card.append(warning);
  }
  if (expanded) {
    card.append(createDeliveryDocketExpandedEditor(row, actions));
  }
  return card;
}

export function createDeliveryDocketExpandedEditor(row, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-attache-expanded-editor workspace-docket-expanded-editor";
  wrapper.append(
    createFormSection("Source Information", [
      createInlineMeta("Source Filename", row.source_filename),
      createInlineMeta("Delivery Docket Number", row.docket_number),
      createInlineMeta("Docket Reference", row.docket_reference),
      createInlineMeta("Delivery Mode", row.delivery_mode),
    ]),
    createAttacheExpandedEditor(row, docketActionAdapter(actions)),
  );
  return wrapper;
}

function docketActionAdapter(actions) {
  return {
    updateDeliveryAttacheImportRow: actions.updateDeliveryDocketImportRow,
    refreshDeliveryAttacheImportRow: (rowId, field, value) =>
      actions.updateDeliveryDocketImportRow(rowId, field, value, { render: true }),
    classifyDeliveryAttacheImportRow: actions.classifyDeliveryDocketImportRow,
    updateDeliveryAttacheImportProductLine: actions.updateDeliveryDocketImportProductLine,
    refreshDeliveryAttacheImportProductLine: (rowId, lineIndex, field, value) =>
      actions.updateDeliveryDocketImportProductLine(
        rowId,
        lineIndex,
        field,
        value,
        { render: true },
      ),
    addDeliveryAttacheImportProductLine: actions.addDeliveryDocketImportProductLine,
    removeDeliveryAttacheImportProductLine: actions.removeDeliveryDocketImportProductLine,
  };
}

export function createDeliveryDocketReviewToolbar(importState, actions) {
  const toolbar = document.createElement("div");
  toolbar.className = "workspace-attache-review-toolbar";
  const selection = document.createElement("div");
  selection.className = "workspace-action-row workspace-attache-selection-row";
  selection.append(
    createActionButton("Select all ready", actions.selectAllReadyDeliveryDocketRows),
    createActionButton("Clear selection", actions.clearDeliveryDocketImportSelection),
  );
  const display = document.createElement("div");
  display.className = "workspace-attache-display-controls";
  const filter = document.createElement("select");
  filter.setAttribute("aria-label", "Filter Delivery Docket reviews");
  [
    ["ALL", "All dockets"],
    ["READY", "Ready"],
    ["WARNING", "Warning"],
    ["DUPLICATE", "Duplicate"],
    ["NOT_IMPORTABLE", "Not importable"],
    ["SELECTED", "Selected"],
  ].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    filter.append(option);
  });
  filter.value = importState.filter || "ALL";
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Search docket, invoice, order or customer";
  search.setAttribute("aria-label", "Search Delivery Docket reviews");
  search.value = importState.search || "";
  const refresh = () => applyAttacheReviewVisibility(
    toolbar.parentElement?.querySelector(".workspace-attache-review-list"),
    search.value,
    filter.value,
  );
  search.addEventListener("input", () => {
    actions.updateDeliveryDocketReviewSearch(search.value);
    refresh();
  });
  filter.addEventListener("change", () => {
    actions.updateDeliveryDocketReviewFilter(filter.value);
    refresh();
  });
  display.append(filter, search);
  toolbar.append(selection, display);
  return toolbar;
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
    createActionButton("Back", actions.backDeliveryImportToSources),
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

export function createDeliveryAttachePreview(importState, actions, {
  showFooter = true,
  showSummary = true,
  headingTitle = "Step 2: Review extracted invoices",
  headingSubtitle = "Check parsed values, expand rows for edits, then confirm selected imports.",
} = {}) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-attache-review-step";
  const rows = importState.rows || [];
  section.append(createSectionHeading(headingTitle, headingSubtitle));
  if (!rows.length) {
    section.append(createEmptyState("No invoice previews yet.", "document"));
    return section;
  }
  if (showSummary) {
    section.append(createAttacheSummaryStrip(rows));
  }
  const selectionRow = createAttacheReviewToolbar(importState, actions);
  const list = document.createElement("div");
  list.className = "workspace-attache-review-list";
  rows.forEach((row) => {
    list.append(createAttacheReviewRow(row, importState, actions));
  });
  applyAttacheReviewVisibility(list, importState.search, importState.filter);
  section.append(selectionRow, list);
  if (showFooter) {
    const selectedCount = countSelectedAttacheRows(rows);
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
    section.append(footer);
  }
  return section;
}

function countSelectedAttacheRows(rows) {
  return (rows || []).filter(
    (row) => row.selected && row.importable && !row.is_duplicate,
  ).length;
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
  card.dataset.invoiceReviewId = row.row_id;
  card.dataset.invoiceSearch = [
    row.invoice_number,
    row.order_no,
    row.company_name,
  ].map((value) => String(value || "").toLowerCase()).join(" ");
  card.dataset.invoiceStatus = attacheRowStatus(row).toUpperCase().replaceAll(" ", "_");
  card.dataset.invoiceSelected = row.selected ? "true" : "false";
  const expanded = Boolean((importState.expandedRowIds || {})[row.row_id]);
  const status = attacheRowStatus(row);
  const header = document.createElement("div");
  header.className = "workspace-attache-review-header";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = Boolean(row.selected);
  checkbox.disabled = importState.isCommitting || row.is_duplicate || !row.importable;
  checkbox.setAttribute("aria-label", `Select invoice ${formatOptional(row.invoice_number, row.row_id)}`);
  checkbox.addEventListener("change", () => actions.toggleDeliveryAttacheImportRow(row.row_id, checkbox.checked));
  const summary = document.createElement("div");
  summary.className = "workspace-attache-review-summary";
  summary.append(
    createBadge(status),
    createInlineMeta("Invoice", row.invoice_number),
    createInlineMeta("Invoice Date", row.invoice_date),
    createInlineMeta("Order", row.order_no),
    createInlineMeta("Customer", row.company_name),
    ...createAttachePaymentMeta(row),
    createInlineMeta("Suburb", row.suburb),
    createInlineMeta("Delivery Area", formatDeliveryAreaLabel(row.delivery_area)),
    createInlineMeta("Region", formatDeliveryRegionLabel(row.auto_delivery_region)),
    createInlineMeta("Delivery Date", row.delivery_date),
    createInlineMeta(
      "Load",
      (row.pallet_quantity || 0) + " pallets / "
        + (row.loose_bags_quantity || 0) + " bags / "
        + (row.carton_quantity || 0) + " cartons",
    ),
  );
  const warning = document.createElement("p");
  warning.className = "workspace-attache-warning-summary";
  warning.textContent = row.is_duplicate
    ? "Duplicate invoice already exists and cannot be selected."
    : (row.warnings || []).join("; ");
  const expand = createActionButton(expanded ? "Collapse" : "Expand", () => {
    const scrollBody = card.closest(".workspace-modal-body");
    const scrollTop = scrollBody?.scrollTop || 0;
    const nextImportState = actions.toggleDeliveryAttacheImportExpanded(row.row_id);
    const currentRow = (nextImportState?.rows || []).find(
      (candidate) => candidate.row_id === row.row_id,
    ) || row;
    const replacement = createAttacheReviewRow(
      currentRow,
      nextImportState || importState,
      actions,
    );
    card.replaceWith(replacement);
    replacement.querySelector("button")?.focus({ preventScroll: true });
    if (scrollBody) {
      scrollBody.scrollTop = scrollTop;
    }
  });
  expand.setAttribute("aria-expanded", String(expanded));
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
      createInlineField("Invoice Date", createInlineInput(row.invoice_date, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "invoice_date", value), "date")),
      createInlineField("Order Number", createInlineInput(row.order_no, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "order_no", value))),
      createInlineField("Company Name", createInlineInput(
        row.company_name,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "company_name", value),
        "text",
        deliveryDocketRowRefreshOptions(actions, row.row_id, "company_name"),
      )),
      createInlineField("Phone", createInlineInput(row.phone, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "phone", value))),
    ]),
    createFormSection("Delivery Details", [
      createInlineField("Delivery Address", createInlineInput(
        row.delivery_address,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_address", value),
        "text",
        deliveryDocketRowRefreshOptions(actions, row.row_id, "delivery_address"),
      )),
      createInlineField("Suburb", createInlineInput(
        row.suburb,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "suburb", value),
        "text",
        { onChange: () => actions.classifyDeliveryAttacheImportRow(row.row_id) },
      )),
      createInlineField("Postcode", createInlineInput(
        row.postcode,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "postcode", value),
        "text",
        { onChange: () => actions.classifyDeliveryAttacheImportRow(row.row_id) },
      )),
      createInlineField("Delivery Date", createInlineInput(
        row.delivery_date,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_date", value),
        "date",
        deliveryDocketRowRefreshOptions(actions, row.row_id, "delivery_date"),
      )),
      createInlineField("Start Time", createInlineInput(row.start_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "start_time", value), "time")),
      createInlineField("End Time", createInlineInput(row.end_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "end_time", value), "time")),
      createInlineField("Urgency", createInlineSelect(row.urgency || "Normal", [
        { value: "Normal", label: "Normal" },
        { value: "Urgent", label: "Urgent" },
      ], (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "urgency", value))),
    ]),
    createFormSection("Delivery Area", [
      createInlineMeta("Effective Area", formatDeliveryAreaLabel(row.delivery_area)),
      createInlineMeta("Region", formatDeliveryRegionLabel(row.auto_delivery_region)),
      createInlineMeta(
        "Source",
        row.delivery_area_source === "MANUAL" ? "Manual Override" : "Automatic",
      ),
    ]),
    createFormSection("Load", [
      createInlineField("Pallet Quantity", createInlineInput(
        row.pallet_quantity,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "pallet_quantity", Number(value || 0)),
        "number",
        deliveryDocketRowRefreshOptions(actions, row.row_id, "pallet_quantity", (value) => Number(value || 0)),
      )),
      createInlineField("Loose Bags Quantity", createInlineInput(
        row.loose_bags_quantity,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "loose_bags_quantity", Number(value || 0)),
        "number",
        deliveryDocketRowRefreshOptions(actions, row.row_id, "loose_bags_quantity", (value) => Number(value || 0)),
      )),
      createInlineField("Carton Quantity", createInlineInput(
        row.carton_quantity,
        (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "carton_quantity", Number(value || 0)),
        "number",
        deliveryDocketRowRefreshOptions(actions, row.row_id, "carton_quantity", (value) => Number(value || 0)),
      )),
    ]),
    createAttacheProductLineEditor(row, actions),
    (row.warnings || []).length
      ? createAttacheWarnings(row.warnings)
      : document.createDocumentFragment(),
    createFormSection("Notes", [createInlineField("Notes", createInlineTextarea(row.note, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "note", value)))]),
  );
  return wrapper;
}

function deliveryDocketRowRefreshOptions(
  actions,
  rowId,
  field,
  normalizeValue = (value) => value,
) {
  const refresh = typeof actions.refreshDeliveryAttacheImportRow === "function"
    ? actions.refreshDeliveryAttacheImportRow
    : null;
  if (!refresh) {
    return {};
  }
  return {
    onChange: (value) => refresh(rowId, field, normalizeValue(value)),
  };
}

export function attacheRowStatus(row) {
  if (row.is_duplicate) {
    return "Duplicate";
  }
  if (hasPaymentEligibility(row)) {
    if (row.payment_eligibility === "PAYMENT_REQUIRED") {
      return "Payment Required";
    }
    if (row.payment_eligibility === "UNKNOWN") {
      return "Needs Review";
    }
  }
  if (!row.importable) {
    return "Not importable";
  }
  if ((row.warnings || []).length) {
    return "Warning";
  }
  return "Ready";
}

function hasPaymentEligibility(row) {
  return Object.prototype.hasOwnProperty.call(row || {}, "payment_eligibility");
}

function createAttachePaymentMeta(row) {
  if (!hasPaymentEligibility(row)) {
    return [];
  }
  const metadata = [
    createInlineMeta(
      "Account Terms",
      row.terms_description || "UNKNOWN",
    ),
  ];
  if (row.terms_description === "C.O.D.") {
    metadata.push(
      createInlineMeta(
        "Outstanding Balance",
        formatOutstandingBalance(row.outstanding_balance),
      ),
    );
  }
  const paymentLabels = {
    NOT_REQUIRED: "Not required",
    PAID_IN_FULL: "Paid in full",
    PAYMENT_REQUIRED: "Payment required",
    UNKNOWN: "Unable to determine",
  };
  metadata.push(createInlineMeta(
    "Payment",
    paymentLabels[row.payment_eligibility] || "Unable to determine",
  ));
  return metadata;
}

function formatOutstandingBalance(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Unavailable";
  }
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-AU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function createInlineMeta(labelText, value) {
  const item = document.createElement("span");
  item.className = "workspace-inline-meta";
  const label = document.createElement("span");
  label.textContent = labelText;
  const content = document.createElement("strong");
  content.textContent = formatOptional(value);
  item.append(label, content);
  return item;
}

export function createMetricPill(labelText, value) {
  const pill = document.createElement("span");
  pill.className = "workspace-metric-pill";
  const label = document.createElement("span");
  label.textContent = labelText;
  const content = document.createElement("strong");
  content.textContent = value;
  pill.append(label, content);
  return pill;
}

export function createAttacheReviewToolbar(importState, actions) {
  const toolbar = document.createElement("div");
  toolbar.className = "workspace-attache-review-toolbar";
  const selection = document.createElement("div");
  selection.className = "workspace-action-row workspace-attache-selection-row";
  selection.append(
    createActionButton("Select all ready", actions.selectAllReadyDeliveryAttacheRows),
    createActionButton("Clear selection", actions.clearDeliveryAttacheImportSelection),
  );
  const display = document.createElement("div");
  display.className = "workspace-attache-display-controls";
  const filter = document.createElement("select");
  filter.setAttribute("aria-label", "Filter invoice reviews");
  const filterOptions = [
    ["ALL", "All invoices"],
    ["READY", "Ready"],
    ["WARNING", "Warning"],
    ["DUPLICATE", "Duplicate"],
    ["NOT_IMPORTABLE", "Not importable"],
    ["SELECTED", "Selected"],
  ];
  if ((importState.rows || []).some(hasPaymentEligibility)) {
    filterOptions.splice(2, 0, ["PAYMENT_REQUIRED", "Payment Required"]);
  }
  filterOptions.forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    filter.append(option);
  });
  filter.value = importState.filter || "ALL";
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Search invoice, order or customer";
  search.setAttribute("aria-label", "Search invoice reviews");
  const refresh = () => {
    applyAttacheReviewVisibility(
      toolbar.parentElement?.querySelector(".workspace-attache-review-list"),
      search.value,
      filter.value,
    );
  };
  search.value = importState.search || "";
  search.addEventListener("input", () => {
    actions.updateDeliveryAttacheReviewSearch(search.value);
    refresh();
  });
  filter.addEventListener("change", () => {
    actions.updateDeliveryAttacheReviewFilter(filter.value);
    refresh();
  });
  display.append(filter, search);
  toolbar.append(selection, display);
  return toolbar;
}

export function applyAttacheReviewVisibility(list, searchValue = "", filterValue = "ALL") {
  if (!list) {
    return;
  }
  const search = String(searchValue || "").trim().toLowerCase();
  [...list.querySelectorAll("[data-invoice-review-id]")].forEach((card) => {
    const matchesSearch = !search || card.dataset.invoiceSearch.includes(search);
    const matchesFilter = filterValue === "ALL"
      || (filterValue === "SELECTED"
        ? card.dataset.invoiceSelected === "true"
        : card.dataset.invoiceStatus === filterValue);
    card.hidden = !(matchesSearch && matchesFilter);
  });
}

function createAttacheWarnings(warnings) {
  const section = document.createElement("section");
  section.className = "workspace-attache-warning-panel";
  const title = document.createElement("h4");
  title.textContent = "Warnings / Parse Issues";
  const list = document.createElement("ul");
  warnings.forEach((warning) => {
    const item = document.createElement("li");
    item.textContent = warning;
    list.append(item);
  });
  section.append(title, list);
  return section;
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
  const lines = row.product_lines || [];
  const section = document.createElement("section");
  section.className = "workspace-product-line-editor";
  const heading = document.createElement("div");
  heading.className = "workspace-load-product-heading";
  const title = document.createElement("h5");
  title.textContent = `Product Lines (${lines.length})`;
  heading.append(title, createActionButton(
    "Add Product Line",
    () => actions.addDeliveryAttacheImportProductLine(row.row_id),
    {
      iconName: "plus",
      className: "workspace-product-line-add",
    },
  ));

  const scroll = document.createElement("div");
  scroll.className = "workspace-product-line-table-scroll";
  scroll.tabIndex = 0;
  scroll.setAttribute("aria-label", "Editable product lines");
  const table = document.createElement("table");
  table.className = "workspace-product-line-table";
  const columns = document.createElement("colgroup");
  [
    "sequence",
    "code",
    "name",
    "actual-quantity",
    "actual-unit",
    "packaging-quantity",
    "packaging-unit",
    "actions",
  ].forEach((name) => columns.append(createAttacheProductLineColumn(name)));
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["#", "Product Code", "Product Name", "Actual Quantity", "Actual Unit", "Packaging Quantity", "Packaging Unit", "Actions"]
    .forEach((label) => {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      headRow.append(cell);
    });
  head.append(headRow);
  const body = document.createElement("tbody");
  const total = document.createElement("p");
  total.className = "workspace-product-line-total";

  lines.forEach((line, index) => {
    const lineRow = document.createElement("tr");
    lineRow.className = "workspace-product-line-table-row";
    lineRow.dataset.productLineId = `${row.row_id}:${index}`;
    lineRow.append(
      createAttacheProductLineCell(String(index + 1), "sequence"),
      createAttacheProductLineCell(createAttacheProductLineInput(
        "Product code",
        line.product_code,
        (value) => actions.updateDeliveryAttacheImportProductLine(
          row.row_id, index, "product_code", value,
        ),
        deliveryDocketProductRefreshOptions(actions, row.row_id, index, "product_code"),
      ), "code"),
      createAttacheProductLineCell(createAttacheProductLineInput(
        "Product name",
        line.product_name,
        (value) => actions.updateDeliveryAttacheImportProductLine(
          row.row_id, index, "product_name", value,
        ),
        deliveryDocketProductRefreshOptions(actions, row.row_id, index, "product_name"),
      ), "name"),
      createAttacheProductLineCell(createAttacheProductLineInput(
        "Actual quantity",
        line.quantity,
        (value) => {
          line.quantity = value;
          actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "quantity", value);
          total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
        },
        {
          type: "number",
          ...deliveryDocketProductRefreshOptions(actions, row.row_id, index, "quantity"),
        },
      ), "actual-quantity"),
      createAttacheProductLineCell(createAttacheProductLineInput(
        "Actual unit",
        line.unit || "KG",
        (value) => {
          line.unit = value;
          actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "unit", value);
          total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
        },
        deliveryDocketProductRefreshOptions(actions, row.row_id, index, "unit"),
      ), "actual-unit"),
      createAttacheProductLineCell(createAttacheProductLineInput(
        "Packaging quantity",
        line.package_quantity,
        (value) => actions.updateDeliveryAttacheImportProductLine(
          row.row_id, index, "package_quantity", value,
        ),
        {
          type: "number",
          ...deliveryDocketProductRefreshOptions(actions, row.row_id, index, "package_quantity"),
        },
      ), "packaging-quantity"),
      createAttacheProductLineCell(createAttacheProductLineInput(
        "Packaging unit",
        line.package_unit,
        (value) => actions.updateDeliveryAttacheImportProductLine(
          row.row_id, index, "package_unit", value,
        ),
        deliveryDocketProductRefreshOptions(actions, row.row_id, index, "package_unit"),
      ), "packaging-unit"),
      createAttacheProductLineCell(createActionButton(
        "Remove product line",
        () => actions.removeDeliveryAttacheImportProductLine(row.row_id, index),
        {
          iconName: "trash",
          iconOnly: true,
          accessibleLabel: `Remove product line ${index + 1}`,
          className: "workspace-product-line-remove",
        },
      ), "actions"),
    );
    body.append(lineRow);
  });
  table.append(columns, head, body);
  scroll.append(table);
  total.textContent = `Total Actual Quantity: ${formatProductLineTotals(lines)}`;
  section.append(heading, scroll, total);
  return section;
}

function createAttacheProductLineInput(
  label,
  value,
  onInput,
  { type = "text", onChange = null } = {},
) {
  const input = document.createElement("input");
  input.type = type;
  input.setAttribute("aria-label", label);
  if (type === "number") {
    input.setAttribute("min", "0");
  }
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  if (onChange) {
    input.addEventListener("change", () => onChange(input.value));
  }
  return input;
}

function createAttacheProductLineColumn(name) {
  const column = document.createElement("col");
  column.className = `workspace-product-column-${name}`;
  return column;
}

function createAttacheProductLineCell(content, name) {
  const cell = document.createElement("td");
  cell.className = `workspace-product-cell-${name}`;
  if (content?.nodeType) {
    cell.append(content);
  } else {
    cell.textContent = content;
  }
  return cell;
}

function deliveryDocketProductRefreshOptions(actions, rowId, lineIndex, field) {
  if (typeof actions.refreshDeliveryAttacheImportProductLine !== "function") {
    return {};
  }
  return {
    onChange: (value) => actions.refreshDeliveryAttacheImportProductLine(
      rowId,
      lineIndex,
      field,
      value,
    ),
  };
}

export function productLineSummary(row) {
  return (row.product_lines || [])
    .map((line, index) => formatProductDetailLine(line, index + 1))
    .join("; ") || "No product lines";
}
