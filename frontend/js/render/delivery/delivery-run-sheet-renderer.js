import { formatOptional } from "../../utils/format-utils.js";

import {
  scopedDeliveryDate,
  createActionButton,
  createSectionHeading,
  createBadge,
  createEmptyState,
  isBusy,
} from "./delivery-renderer-utils.js";

export function createRunSheetList(runSheets, state, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-run-sheets";
  const deliveryDate = scopedDeliveryDate(state);
  const filtered = (runSheets || []).filter((runSheet) => (
    runSheet.delivery_date === deliveryDate
    && ["GENERATED", "SAVED"].includes(runSheet.status)
  ));

  wrapper.append(
    createRunSheetToolbar(deliveryDate, state, actions),
    createRunSheetDateGroup(deliveryDate, filtered, state, actions),
  );
  return wrapper;
}

export function createRunSheetToolbar(deliveryDate, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-context-panel workspace-context-panel-delivery workspace-run-sheet-intro";
  panel.append(createSectionHeading(
    "Delivery Run Sheets",
    "Review generated and saved Delivery Run Sheets by actual Delivery date.",
  ));
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-delivery-date-control";
  field.textContent = "Delivery date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = deliveryDate;
  input.disabled = state.isDeliveryWorkspaceLoading;
  input.addEventListener("change", () => actions.updateDeliveryTripSummaryDate(input.value));
  field.append(input);
  panel.append(field);
  return panel;
}

export function createRunSheetDateGroup(deliveryDate, runSheets, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-delivery workspace-run-sheet-date-group";
  const header = document.createElement("div");
  header.className = "workspace-record-card-top workspace-run-sheet-date-group-header";
  header.append(createSectionHeading(
    `Delivery date: ${deliveryDate}`,
    `${runSheets.length} generated/saved run sheets for this Delivery Date`,
  ));
  const exportKey = `delivery-export-date:${deliveryDate}`;
  const isExporting = isBusy(state, exportKey);
  const exportButton = createActionButton(
    isExporting ? "Preparing Excel File..." : "Export Excel File",
    () => actions.exportDeliveryRunSheets(deliveryDate),
    {
      disabled: isExporting || !runSheets.length,
    },
  );
  exportButton.dataset.deliveryRunSheetExport = deliveryDate;
  header.append(exportButton);
  section.append(header);
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-run-sheet-grid workspace-run-sheet-paper-list";
  if (!runSheets.length) {
    grid.append(createEmptyState(
      "No generated or saved Delivery Run Sheets for this Delivery Date.",
      "history",
    ));
  } else {
    runSheets.forEach((runSheet) => grid.append(
      createRunSheetDocumentCard(runSheet, state, actions),
    ));
  }
  section.append(grid);
  return section;
}

export function createDailyRunSheetPaper(
  runSheet,
  state,
  actions,
  { context = "operational", embedded = false } = {},
) {
  const isHistory = context === "history";
  const paper = document.createElement("article");
  paper.className = "workspace-daily-run-sheet";

  const header = document.createElement("header");
  header.className = "workspace-daily-run-sheet-header";
  header.append(
    createDailyRunSheetHeaderField("DATE:", formatDailyRunSheetDate(runSheet.delivery_date)),
    createDailyRunSheetTitle(),
    createDailyRunSheetDriverHeader(runSheet),
  );

  const metadata = document.createElement("div");
  metadata.className = "workspace-daily-run-sheet-metadata";
  const metadataValues = [
    `Generated: ${formatOptional(runSheet.generated_at)}`,
  ];
  if (isHistory) {
    metadataValues.push(
      `Saved: ${formatOptional(runSheet.saved_at)}`,
      `Saved by: ${formatOptional(runSheet.saved_by_account_name, "Unknown")}`,
      `Workspace date: ${formatOptional(runSheet.dispatch_date)}`,
    );
  }
  metadataValues.forEach((value) => {
    const item = document.createElement("span");
    item.textContent = value;
    metadata.append(item);
  });
  metadata.append(createBadge(
    runSheet.status,
    String(runSheet.status || "").toLowerCase(),
  ));

  const operationalFields = document.createElement("div");
  operationalFields.className = "workspace-daily-run-sheet-operational-fields";
  [
    "START TIME: ______________________",
    "TIME LOADING STARTED (TO BE FILLED IN BY STOREMAN): ______________________",
    "TIME LOADING COMPLETED (TO BE FILLED IN BY STOREMAN): ______________________",
  ].forEach((label) => {
    const field = document.createElement("p");
    field.textContent = label;
    operationalFields.append(field);
  });

  const tableRegion = document.createElement("div");
  tableRegion.className = "workspace-daily-run-sheet-table-scroll";
  tableRegion.tabIndex = 0;
  tableRegion.setAttribute("aria-label", "Daily Run Sheet order table");
  const table = document.createElement("table");
  table.className = "workspace-daily-run-sheet-table";
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  DAILY_RUN_SHEET_COLUMNS.forEach((column) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = column;
    headerRow.append(cell);
  });
  head.append(headerRow);
  const body = document.createElement("tbody");
  dailyRunSheetSnapshotRows(runSheet).forEach((order, rowIndex) => {
    const row = document.createElement("tr");
    dailyRunSheetRowValues(order, rowIndex + 1).forEach((value, columnIndex) => {
      const cell = document.createElement("td");
      if (columnIndex === 4) {
        cell.classList.add("workspace-daily-run-sheet-product-cell");
      }
      cell.textContent = value;
      row.append(cell);
    });
    body.append(row);
  });
  table.append(head, body);
  tableRegion.append(table);

  const finish = document.createElement("p");
  finish.className = "workspace-daily-run-sheet-finish";
  finish.textContent = "FINISH TIME: ______________________";

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-daily-run-sheet-actions";
  if (isHistory) {
    const isExporting = isBusy(state, `delivery-export:${runSheet.run_sheet_id}`);
    actionsRow.append(createActionButton(
      isExporting ? "Exporting..." : "Export Excel",
      () => actions.exportDeliveryRunSheet(runSheet.run_sheet_id),
      { disabled: isExporting, primary: true },
    ));
  } else {
    actionsRow.append(
      createActionButton(
        "Save Run Sheet",
        () => actions.saveDeliveryRunSheet(runSheet.run_sheet_id),
        {
          disabled: isBusy(state, `delivery-save:${runSheet.run_sheet_id}`),
          primary: true,
        },
      ),
      createActionButton(
        "Cancel Generated",
        () => actions.cancelDeliveryRunSheet(runSheet.run_sheet_id),
        {
          disabled: isBusy(state, `delivery-cancel:${runSheet.run_sheet_id}`),
        },
      ),
    );
  }
  paper.append(header);
  if (!embedded) {
    paper.append(metadata);
  }
  paper.append(operationalFields, tableRegion, finish);
  if (!embedded) {
    paper.append(actionsRow);
  }
  return paper;
}

const DAILY_RUN_SHEET_COLUMNS = [
  "",
  "Customer Name",
  "Suburb",
  "Invoice #",
  "PRODUCT",
  "KG'S",
  "Pallets",
  "COD",
  "CQ",
  "Time In",
  "Time Out",
  "PRINT NAME",
  "SIGNATURE",
  "NO. # PALLETS RETND",
];

export function createDailyRunSheetHeaderField(labelText, valueText, className = "") {
  const field = document.createElement("div");
  field.className = `workspace-daily-run-sheet-header-field ${className}`.trim();
  const label = document.createElement("span");
  label.textContent = labelText;
  const value = document.createElement("strong");
  value.textContent = valueText;
  field.append(label, value);
  return field;
}

export function createDailyRunSheetDriverHeader(runSheet) {
  const field = document.createElement("div");
  field.className = "workspace-daily-run-sheet-header-field workspace-daily-run-sheet-driver";
  [
    ["DRIVER:", formatOptional(runSheet.driver_name_snapshot, runSheet.driver_id)],
    ["REGO#:", formatOptional(runSheet.vehicle_rego_snapshot, "Not selected")],
  ].forEach(([labelText, valueText]) => {
    const row = document.createElement("div");
    row.className = "workspace-daily-run-sheet-driver-line";
    const line = document.createElement("strong");
    line.textContent = `${labelText} ${valueText}`;
    row.append(line);
    field.append(row);
  });
  return field;
}

export function createDailyRunSheetTitle() {
  const title = document.createElement("h3");
  title.className = "workspace-daily-run-sheet-title";
  title.textContent = "DAILY RUN SHEET";
  return title;
}

export function dailyRunSheetSnapshotRows(runSheet) {
  return (runSheet.trips || []).flatMap((trip) => trip.orders || []);
}

export function dailyRunSheetRowValues(order, rowNumber) {
  return [
    formatRunSheetNumber(rowNumber),
    formatOptional(order.company_name_snapshot, ""),
    formatOptional(order.suburb_snapshot, ""),
    formatOptional(order.invoice_number_snapshot || order.order_no_snapshot, ""),
    formatRunSheetProduct(order),
    "",
    formatRunSheetNumber(order.pallet_quantity_snapshot),
    "",
    "",
    "",
    "",
    "",
    "",
    "",
  ];
}

export function formatRunSheetProduct(order) {
  const names = [];
  const seen = new Set();
  (order.product_lines_snapshot || []).forEach((line) => {
    const productName = String(line?.product_name || "").trim();
    if (!productName) {
      return;
    }
    const key = productName.replace(/\s+/g, " ").toLocaleLowerCase();
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    names.push(productName);
  });
  if (names.length) {
    return names.join("\n");
  }
  return String(order.product_snapshot || "").trim();
}

export function formatRunSheetNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? String(numericValue) : "";
}

export function formatDailyRunSheetDate(value) {
  const [year, month, day] = String(value || "").split("-");
  return year && month && day ? `${day}/${month}/${year}` : "";
}

export function createRunSheetDocumentCard(runSheet, state, actions) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-run-sheet-document-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.className = "workspace-record-kicker";
  kicker.textContent = runSheet.delivery_date;
  const heading = document.createElement("h3");
  heading.textContent = formatOptional(runSheet.driver_name_snapshot, runSheet.driver_id);
  identity.append(kicker, heading);
  top.append(identity, createBadge(runSheet.status, runSheet.status.toLowerCase()));

  const meta = document.createElement("p");
  meta.className = "workspace-run-sheet-card-meta";
  const metadata = [
    `Workspace date: ${formatOptional(runSheet.dispatch_date)}`,
    `Delivery date: ${formatOptional(runSheet.delivery_date)}`,
    `Driver: ${formatOptional(runSheet.driver_name_snapshot, runSheet.driver_id)}`,
    `Status: ${formatOptional(runSheet.status)}`,
    `Generated: ${formatOptional(runSheet.generated_at)}`,
  ];
  if (runSheet.status === "SAVED") {
    metadata.push(
      `Saved: ${formatOptional(runSheet.saved_at)}`,
      `Saved by: ${formatOptional(runSheet.saved_by_account_name, "Unknown")}`,
    );
  }
  meta.textContent = metadata.join(" | ");

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-run-sheet-actions";
  if (runSheet.status === "GENERATED") {
    actionsRow.append(
      createActionButton("Save Run Sheet", () => actions.saveDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-save:${runSheet.run_sheet_id}`),
        primary: true,
      }),
      createActionButton("Cancel Generated", () => actions.cancelDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-cancel:${runSheet.run_sheet_id}`),
      }),
    );
  }
  if (runSheet.status === "SAVED") {
    const isExporting = isBusy(state, `delivery-export:${runSheet.run_sheet_id}`);
    actionsRow.append(
      createActionButton(
        isExporting ? "Exporting..." : "Export Excel",
        () => actions.exportDeliveryRunSheet(runSheet.run_sheet_id),
        { disabled: isExporting, primary: true },
      ),
    );
  }
  card.append(
    top,
    meta,
    createDailyRunSheetPaper(runSheet, state, actions, { embedded: true }),
    actionsRow,
  );
  return card;
}
