import { DEFAULT_DISPATCH_DATE, state } from "../state/app-state.js";
import {
  createBadge,
  createDetailField,
  createOption,
} from "../utils/dom-utils.js";
import {
  formatOptional,
  formatOrderLoadQuantity,
  formatProductDetailLine,
} from "../utils/format-utils.js";

export function renderFinalTripSummaries({
  getUnsavedFinalSummaries,
  normalizeFinalSummary,
  onHistoryDateChange,
  onLoadFinalSummaryHistory,
  onSaveAllFinalSummaries,
  syncHistoryDateSelection,
}) {
  renderFinalSummaryControls({
    getUnsavedFinalSummaries,
    onHistoryDateChange,
    onLoadFinalSummaryHistory,
    onSaveAllFinalSummaries,
    syncHistoryDateSelection,
  });

  const finalSummaryList = document.querySelector("#final-trip-summary-list");
  if (!finalSummaryList) {
    return;
  }

  finalSummaryList.innerHTML = "";
  const summaries = Object.values(state.finalTripSummaries)
    .map(normalizeFinalSummary)
    .filter((summary) =>
      summary.dispatch_date === state.dispatchDate &&
      summary.delivery_date === state.driverSummaryDeliveryDate,
    );

  if (summaries.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = "No generated Final Trip Summary previews for this delivery date.";
    finalSummaryList.append(emptyState);
  } else {
    summaries
      .sort((first, second) => first.driver_name.localeCompare(second.driver_name))
      .forEach((summary) => {
        finalSummaryList.append(createFinalTripSummaryCard(summary, { mode: "preview" }));
      });
  }

  renderFinalSummaryHistory({ normalizeFinalSummary });
}

function renderFinalSummaryControls({
  getUnsavedFinalSummaries,
  onHistoryDateChange,
  onLoadFinalSummaryHistory,
  onSaveAllFinalSummaries,
  syncHistoryDateSelection,
}) {
  const saveButton = document.querySelector("#save-final-summary-button");
  const historyDateSelect = document.querySelector("#history-date-select");
  const loadHistoryButton = document.querySelector("#load-history-button");
  const message = document.querySelector("#final-summary-control-message");
  const unsavedSummaries = getUnsavedFinalSummaries();

  if (saveButton) {
    saveButton.disabled =
      !state.isLoggedIn ||
      state.isLoading ||
      state.isSaving ||
      state.isSavingFinalSummaries ||
      unsavedSummaries.length === 0;
    saveButton.textContent = state.isSavingFinalSummaries
      ? "Saving and Exporting..."
      : "Save and Export";
    saveButton.onclick = () => {
      onSaveAllFinalSummaries();
    };
  }

  if (historyDateSelect) {
    syncHistoryDateSelection();
    const dateOptions = state.finalSummaryDates.length
      ? state.finalSummaryDates
      : [state.historyDate || state.dispatchDate || DEFAULT_DISPATCH_DATE];
    historyDateSelect.innerHTML = "";
    dateOptions.forEach((date) => {
      historyDateSelect.append(createOption(date, date, date === state.historyDate));
    });
    historyDateSelect.disabled = state.isLoading || state.isSaving || state.isHistoryLoading;
    historyDateSelect.onchange = () => {
      onHistoryDateChange(historyDateSelect.value || state.dispatchDate);
    };
  }

  if (loadHistoryButton) {
    loadHistoryButton.disabled = state.isLoading || state.isSaving || state.isHistoryLoading;
    loadHistoryButton.textContent = state.isHistoryLoading ? "Loading History..." : "Load History";
    loadHistoryButton.onclick = () => {
      onLoadFinalSummaryHistory();
    };
  }

  if (message) {
    const loginBlocked = !state.isLoggedIn && unsavedSummaries.length > 0;
    const helperMessage =
      loginBlocked
        ? "Please log in before saving and exporting Final Trip Summary."
        : unsavedSummaries.length === 0
        ? "No unsaved Final Summary to save and export."
        : `${unsavedSummaries.length} generated summary${
            unsavedSummaries.length === 1 ? "" : "ies"
          } ready to save and export.`;
    const text =
      state.finalSummaryGlobalSaveError ||
      state.finalSummaryGlobalSaveSuccess ||
      helperMessage;
    message.className =
      state.finalSummaryGlobalSaveError || loginBlocked ? "board-error" : "board-status";
    message.hidden = false;
    message.textContent = text;
  }
}

function renderFinalSummaryHistory({ normalizeFinalSummary }) {
  const historyList = document.querySelector("#final-summary-history-list");
  if (!historyList) {
    return;
  }

  historyList.innerHTML = "";

  if (state.isHistoryLoading) {
    const loadingState = document.createElement("p");
    loadingState.className = "empty-board";
    loadingState.textContent = "Loading saved Final Trip Summary history...";
    historyList.append(loadingState);
    return;
  }

  if (state.historyError) {
    const error = document.createElement("p");
    error.className = "board-error";
    error.textContent = state.historyError;
    historyList.append(error);
    return;
  }

  if (!state.historyLoaded) {
    const prompt = document.createElement("p");
    prompt.className = "empty-board";
    prompt.textContent = "Choose a History Date and click Load History to view saved Final Trip Summaries.";
    historyList.append(prompt);
    return;
  }

  if (state.finalSummaryHistory.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = `No saved Final Trip Summaries found for ${state.historyDate}.`;
    historyList.append(emptyState);
    return;
  }

  const heading = document.createElement("p");
  heading.className = "filter-summary";
  heading.textContent = `${state.finalSummaryHistory.length} saved Final Trip Summary${
    state.finalSummaryHistory.length === 1 ? "" : "ies"
  } for ${state.historyDate}.`;
  historyList.append(heading);

  state.finalSummaryHistory
    .map(normalizeFinalSummary)
    .sort((first, second) => first.driver_name.localeCompare(second.driver_name))
    .forEach((summary) => {
      historyList.append(createFinalTripSummaryCard(summary, { mode: "history" }));
    });
}

function createFinalTripSummaryCard(summary, options = {}) {
  const card = document.createElement("article");
  card.className = "final-summary-card";
  const isSaved = Boolean(summary.summary_id);

  const header = document.createElement("div");
  header.className = "final-summary-header";

  const titleWrap = document.createElement("div");
  if (options.mode === "history") {
    const kicker = document.createElement("p");
    kicker.className = "section-kicker";
    kicker.textContent = "Saved history";
    titleWrap.append(kicker);
  }

  const title = document.createElement("h3");
  title.textContent = summary.driver_name;

  titleWrap.append(title);

  const actions = document.createElement("div");
  actions.className = "final-summary-actions";
  actions.append(createBadge(isSaved ? "Saved" : "Locked", "good"));
  header.append(titleWrap, actions);

  const meta = document.createElement("dl");
  meta.className = "final-summary-meta";
  meta.append(
    createDetailField("Dispatch Date", summary.dispatch_date),
    createDetailField("Delivery Date", summary.delivery_date),
    createDetailField("Driver", summary.driver_name),
    createDetailField("Rego #", summary.vehicle_rego),
    createDetailField(
      isSaved ? "Saved by" : "Will be saved by",
      summary.saved_by_account_name || "Unknown",
    ),
    createDetailField("Total Pallets", summary.total_pallets),
    createDetailField("Total Loose Bags", summary.total_loose_bags),
  );

  const trips = document.createElement("div");
  trips.className = "final-summary-trips";

  let rowNumber = 1;
  summary.trips.forEach((trip) => {
    if (trip.orders.length === 0) {
      return;
    }

    const tripSection = document.createElement("section");
    tripSection.className = "final-trip-section";

    const heading = document.createElement("h4");
    heading.textContent = trip.trip_no === "trip1" ? "Trip 1" : "Trip 2";

    const table = document.createElement("table");
    table.className = "final-trip-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    ["No.", "Customer Name", "Suburb", "Invoice #", "Product Details", "Load"].forEach((label) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      headerRow.append(th);
    });
    thead.append(headerRow);

    const tbody = document.createElement("tbody");
    trip.orders.forEach((order) => {
      const row = document.createElement("tr");
      [
        rowNumber,
        formatOptional(order.company_name, ""),
        formatOptional(order.suburb, ""),
        formatOptional(order.invoice_number, ""),
        formatProductDetails(order),
        formatOrderLoadQuantity(order),
      ].forEach((value, columnIndex) => {
        const td = document.createElement("td");
        td.textContent = value;
        if (columnIndex === 4) {
          td.className = "final-summary-product-details";
        }
        row.append(td);
      });
      tbody.append(row);
      rowNumber += 1;
    });

    table.append(thead, tbody);
    tripSection.append(heading, table);
    trips.append(tripSection);
  });

  card.append(header, meta, trips);
  return card;
}

function formatProductDetails(order) {
  const productLines = order.product_lines_snapshot || order.product_lines || [];
  if (!productLines.length) {
    return "No product details recorded.";
  }
  return productLines
    .map((line, index) => formatProductDetailLine(line, index + 1))
    .join("\n");
}
