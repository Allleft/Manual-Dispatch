import { createDeliveryAttacheImportModal } from "./delivery/delivery-attache-modal-renderer.js";

import { createDeliveryGenerationConfirmationModal } from "./delivery/delivery-generation-modal-renderer.js";

import { createSavedRunSheetHistory } from "./delivery/delivery-history-renderer.js";

import { createDeliveryOrderModal } from "./delivery/delivery-order-modal-renderer.js";

import { createStatus } from "./delivery/delivery-renderer-utils.js";

import { createRunSheetList } from "./delivery/delivery-run-sheet-renderer.js";

import { createDeliverySpecificationModal } from "./delivery/delivery-specification-modal-renderer.js";

import { createDeliveryTaskPool } from "./delivery/delivery-task-pool-renderer.js";

import { createDeliveryTripSummary } from "./delivery/delivery-trip-summary-renderer.js";

import { createWorkspacePage } from "./delivery/delivery-workspace-page.js";

export function renderDeliveryWorkspace(
  root,
  { state, actions, onDispatchDateChange },
) {
  root.innerHTML = "";
  const page = createWorkspacePage(state, onDispatchDateChange);
  const content = document.createElement("div");
  content.className = "workspace-content";

  if (state.isDeliveryWorkspaceLoading) {
    content.append(createStatus(
      state.workspaceRoute === "delivery/history"
        ? "Loading saved Delivery Run Sheet history..."
        : "Loading Order Delivery workspace...",
      "loading",
    ));
  } else if (state.deliveryWorkspaceError) {
    content.append(createStatus(state.deliveryWorkspaceError, "error"));
  } else {
    if (state.deliveryActionError) {
      content.append(createStatus(state.deliveryActionError, "error"));
    }
    if (state.workspaceRoute === "delivery/task-pool") {
      content.append(createDeliveryTaskPool(state.deliveryBoard, state, actions));
    } else if (state.workspaceRoute === "delivery/trip-summary") {
      content.append(createDeliveryTripSummary(
        state.deliveryTripSummaryBoard,
        state,
        actions,
      ));
    } else if (state.workspaceRoute === "delivery/history") {
      content.append(createSavedRunSheetHistory(state, actions));
    } else {
      content.append(createRunSheetList(state.deliveryRunSheets, state, actions));
    }
  }

  page.append(content);
  page.append(
    createDeliveryOrderModal(state, actions),
    createDeliveryAttacheImportModal(state, actions),
    createDeliverySpecificationModal(state, actions),
  );
  if (
    state.workspaceRoute === "delivery/trip-summary"
    && state.deliveryGenerationConfirmation
  ) {
    page.append(createDeliveryGenerationConfirmationModal(state, actions));
  }
  root.append(page);
}
