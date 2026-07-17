import { createCollectionCard } from "./opshop-collection-renderer.js";

import {
  createSectionHeading,
  createEmptyState,
} from "./opshop-renderer-utils.js";

export function createSavedPickupCollectionHistory(state, actions) {
  const collections = state.opshopSavedHistoryCollections || [];
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-saved-history";

  const toolbar = document.createElement("section");
  toolbar.className =
    "workspace-context-panel workspace-context-panel-opshop workspace-history-toolbar";
  const heading = createSectionHeading(
    "Saved Pickup Collection History",
    "Search saved OP SHOP Pickup Collections by their actual Pickup Date.",
  );
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-opshop-pickup-date-control";
  field.textContent = "Pickup date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = state.opshopSavedHistoryDate || "";
  input.disabled = state.isOpShopWorkspaceLoading;
  input.addEventListener("change", () =>
    actions.updateOpShopSavedHistoryDate(input.value));
  field.append(input);
  toolbar.append(heading, field);

  const results = document.createElement("section");
  results.className =
    "workspace-context-panel workspace-context-panel-opshop workspace-history-results";
  results.append(createSectionHeading(
    "Saved Pickup Collections",
    `${collections.length} records`,
  ));
  const list = document.createElement("div");
  list.className =
    "workspace-card-grid workspace-collection-grid workspace-pickup-collection-paper-list";
  if (!collections.length) {
    list.append(createEmptyState(
      "No saved Pickup Collections were found for this Pickup Date.",
      "history",
    ));
  } else {
    collections.forEach((collection) => list.append(
      createCollectionCard(collection, state, actions, { historyMode: true }),
    ));
  }
  results.append(list);
  wrapper.append(toolbar, results);
  return wrapper;
}
