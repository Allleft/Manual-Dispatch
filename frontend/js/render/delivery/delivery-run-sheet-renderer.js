import {
  formatOptional,
  formatProductDetailLine,
} from "../../utils/format-utils.js";

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
  metadataValues.push(
    `Execution: ${formatOptional(runSheet.execution_status, "OPEN")}`,
  );
  if ((runSheet.execution_status || "OPEN") === "CLOSED") {
    metadataValues.push(
      `Closed: ${formatOptional(runSheet.closed_at)}`,
      `Closed by: ${formatOptional(runSheet.closed_by_account_name, "Unknown")}`,
      `Delivered: ${Number(runSheet.closeout_summary?.delivered_count || 0)}`,
      `Returned to pool: ${Number(runSheet.closeout_summary?.returned_to_pool_count || 0)}`,
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
  metadata.append(createBadge(
    runSheet.execution_status || "OPEN",
    String(runSheet.execution_status || "OPEN").toLowerCase(),
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
  if (isHistory && (runSheet.outcomes || []).length) {
    paper.append(createRunSheetOutcomeDetails(runSheet));
  }
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
  "Loose Bags",
  "Cartons",
  "Notes",
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
    formatRunSheetKgTotal(order),
    formatRunSheetNumber(order.pallet_quantity_snapshot),
    formatRunSheetNumber(order.loose_bags_quantity_snapshot),
    formatRunSheetNumber(order.carton_quantity_snapshot),
    formatOptional(order.note_snapshot, ""),
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
  const productLines = order.product_lines_snapshot || [];
  if (productLines.length) {
    return productLines
      .map((line, index) => formatProductDetailLine(line, index + 1))
      .join("\n");
  }
  return String(order.product_snapshot || "").trim();
}

export function formatRunSheetKgTotal(order) {
  const total = (order.product_lines_snapshot || [])
    .filter((line) => ["KG", "KGS"].includes(String(line.unit || "").toUpperCase()))
    .reduce((sum, line) => sum + Number(line.quantity || 0), 0);
  return total > 0 ? formatRunSheetNumber(total) : "";
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
  const badges = document.createElement("div");
  badges.className = "workspace-run-sheet-badges";
  badges.append(
    createBadge(runSheet.status, runSheet.status.toLowerCase()),
    createBadge(
      runSheet.execution_status || "OPEN",
      String(runSheet.execution_status || "OPEN").toLowerCase(),
    ),
  );
  top.append(identity, badges);

  const meta = document.createElement("p");
  meta.className = "workspace-run-sheet-card-meta";
  const metadata = [
    `Workspace date: ${formatOptional(runSheet.dispatch_date)}`,
    `Delivery date: ${formatOptional(runSheet.delivery_date)}`,
    `Driver: ${formatOptional(runSheet.driver_name_snapshot, runSheet.driver_id)}`,
    `Status: ${formatOptional(runSheet.status)}`,
    `Execution: ${formatOptional(runSheet.execution_status, "OPEN")}`,
    `Generated: ${formatOptional(runSheet.generated_at)}`,
  ];
  if (runSheet.status === "SAVED") {
    metadata.push(
      `Saved: ${formatOptional(runSheet.saved_at)}`,
      `Saved by: ${formatOptional(runSheet.saved_by_account_name, "Unknown")}`,
    );
  }
  if ((runSheet.execution_status || "OPEN") === "CLOSED") {
    metadata.push(
      `Delivered: ${Number(runSheet.closeout_summary?.delivered_count || 0)}`,
      `Returned to pool: ${Number(runSheet.closeout_summary?.returned_to_pool_count || 0)}`,
      `Closed: ${formatOptional(runSheet.closed_at)}`,
      `Closed by: ${formatOptional(runSheet.closed_by_account_name, "Unknown")}`,
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
    const isOpen = (runSheet.execution_status || "OPEN") === "OPEN";
    const isClosing = isBusy(
      state,
      `delivery-closeout:${runSheet.run_sheet_id}`,
    );
    if (isOpen) {
      actionsRow.append(
        createActionButton(
          isClosing ? "Closing..." : "Close Run Sheet",
          () => actions.openDeliveryRunSheetCloseout(runSheet.run_sheet_id),
          { disabled: isClosing, primary: true },
        ),
      );
    }
    actionsRow.append(
      createActionButton(
        isExporting ? "Exporting..." : "Export Excel",
        () => actions.exportDeliveryRunSheet(runSheet.run_sheet_id),
        { disabled: isExporting },
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

export function createRunSheetOutcomeDetails(runSheet) {
  const section = document.createElement("section");
  section.className = "workspace-run-sheet-outcomes";
  const heading = document.createElement("h4");
  heading.textContent = "Closeout outcomes";
  section.append(heading);
  const outcomesByRow = new Map(
    (runSheet.outcomes || []).map((outcome) => [
      outcome.run_sheet_row_id,
      outcome,
    ]),
  );
  const list = document.createElement("div");
  list.className = "workspace-run-sheet-outcome-list";
  dailyRunSheetSnapshotRows(runSheet).forEach((order) => {
    const outcome = outcomesByRow.get(order.row_id);
    if (!outcome) {
      return;
    }
    const item = document.createElement("article");
    item.className = "workspace-run-sheet-outcome";
    const title = document.createElement("strong");
    title.textContent = [
      formatOptional(
        order.invoice_number_snapshot || order.order_no_snapshot,
        order.order_id_snapshot,
      ),
      formatOptional(order.company_name_snapshot),
    ].join(" - ");
    const detail = document.createElement("span");
    detail.textContent = outcome.outcome === "DELIVERED"
      ? "Delivered"
      : [
        "Returned to Delivery Task Pool",
        `Next date: ${formatOptional(outcome.next_delivery_date)}`,
        `Reason: ${formatOptional(outcome.reason_code)}`,
        outcome.note ? `Note: ${outcome.note}` : "",
      ].filter(Boolean).join(" | ");
    item.append(title, detail);
    list.append(item);
  });
  section.append(list);
  return section;
}
