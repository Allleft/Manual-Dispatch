import {
  createSectionHeading,
  createEmptyState,
} from "./delivery-renderer-utils.js";

import { createDailyRunSheetPaper } from "./delivery-run-sheet-renderer.js";

export function createSavedRunSheetHistory(state, actions) {
  const runSheets = state.deliverySavedHistoryRunSheets || [];
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-saved-history";

  const toolbar = document.createElement("section");
  toolbar.className =
    "workspace-context-panel workspace-context-panel-delivery workspace-history-toolbar";
  const heading = createSectionHeading("Saved Run Sheet History");
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-delivery-date-control";
  field.textContent = "Delivery date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = state.deliverySavedHistoryDate || "";
  input.disabled = state.isDeliveryWorkspaceLoading;
  input.addEventListener("change", () =>
    actions.updateDeliverySavedHistoryDate(input.value));
  field.append(input);
  toolbar.append(heading, field);

  const results = document.createElement("section");
  results.className =
    "workspace-context-panel workspace-context-panel-delivery workspace-history-results";
  results.append(createSectionHeading("Saved Run Sheets", `${runSheets.length} records`));
  const list = document.createElement("div");
  list.className =
    "workspace-card-grid workspace-daily-run-sheet-list workspace-run-sheet-paper-list";
  if (!runSheets.length) {
    list.append(createEmptyState(
      "No saved Delivery Run Sheets were found for this Delivery Date.",
      "history",
    ));
  } else {
    runSheets.forEach((runSheet) => list.append(
      createDailyRunSheetPaper(runSheet, state, actions, { context: "history" }),
    ));
  }
  results.append(list);
  wrapper.append(toolbar, results);
  return wrapper;
}
