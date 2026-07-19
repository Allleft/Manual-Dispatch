import { createCollectionList } from "./opshop/opshop-collection-renderer.js";

import { createSavedPickupCollectionHistory } from "./opshop/opshop-history-renderer.js";

import {
  createStatus,
  isBusy,
} from "./opshop/opshop-renderer-utils.js";

import { createOpShopTaskPool } from "./opshop/opshop-task-pool-renderer.js";

import { createTemplateManagementPage } from "./opshop/opshop-template-page-renderer.js";

import { createOpShopTripSummary } from "./opshop/opshop-trip-summary-renderer.js";

import { createWorkspacePage } from "./opshop/opshop-workspace-page.js";

import {
  openCountrysideRouteGroupDetailModal,
  openOpShopPickupDetailModal,
  openOpShopPickupCollectionConfirmationModal,
} from "../utils/opshop-workspace-modal-utils.js";

export function renderOpShopWorkspace(
  root,
  { state, actions, onDispatchDateChange },
) {
  root.innerHTML = "";
  const page = createWorkspacePage(state, onDispatchDateChange);
  const content = document.createElement("div");
  content.className = "workspace-content";

  if (state.isOpShopWorkspaceLoading) {
    content.append(createStatus(
      state.workspaceRoute === "opshop/history"
        ? "Loading saved Pickup Collection history..."
        : "Loading OP SHOP Pickup workspace...",
      "loading",
    ));
  } else if (state.opshopWorkspaceError) {
    content.append(createStatus(state.opshopWorkspaceError, "error"));
  } else {
    if (state.opshopActionError) {
      content.append(createStatus(state.opshopActionError, "error"));
    }
    if (state.workspaceRoute === "opshop/templates") {
      content.append(createTemplateManagementPage(state, actions));
    } else if (state.workspaceRoute === "opshop/trip-summary") {
      content.append(createOpShopTripSummary(
        state.opshopTripSummaryBoard,
        state.opshopTripSummaryCollections,
        state,
        actions,
        (pickup, trigger) => openOpShopPickupDetailModal(root, { pickup, trigger }),
      ));
    } else if (state.workspaceRoute === "opshop/collections") {
      content.append(
        createCollectionList(
          state.opshopPickupCollections,
          state,
          actions,
        ),
      );
    } else if (state.workspaceRoute === "opshop/history") {
      content.append(createSavedPickupCollectionHistory(state, actions));
    } else {
      content.append(createOpShopTaskPool(
        state.opshopBoard,
        state,
        actions,
        (detail) => openCountrysideRouteGroupDetailModal(root, detail),
      ));
    }
  }

  page.append(content);
  root.append(page);
  if (
    state.workspaceRoute === "opshop/trip-summary"
    && state.opshopGenerationConfirmation
  ) {
    const confirmation = state.opshopGenerationConfirmation;
    openOpShopPickupCollectionConfirmationModal(root, {
      confirmation,
      isGenerating: isBusy(
        state,
        `opshop-generate:${confirmation.pickup_date}:${confirmation.driver_id}`,
      ),
      onCancel: actions.closeOpShopGenerationConfirmation,
      onConfirm: actions.confirmGenerateOpShopPickupCollection,
    });
  }
}
