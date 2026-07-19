import { formatOptional } from "../../utils/format-utils.js";

import {
  readyPickupCollectionCandidates,
  assignedOpShopPickupsForDriver,
  findPickupCollectionForDriver,
  pickupCategoryCounts,
  isCountrysidePickup,
  isRegularPickup,
  isOncallPickup,
  pickupCategoryLabel,
  currentDriverId,
  createActionButton,
  createMetricGrid,
  createSectionHeading,
  appendFact,
  createBadge,
  createStatus,
  createEmptyState,
  isBusy,
} from "./opshop-renderer-utils.js";

export function createOpShopTripSummary(board, collections, state, actions, onOpenPickupDetail) {
  if (!board) {
    return createEmptyState("No OP SHOP workspace data loaded.", "store");
  }
  const pickupDate = state.opshopTripSummaryDate || state.dispatchDate;
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-opshop-trip-summary";
  wrapper.append(createOpShopTripSummaryToolbar(pickupDate, state, actions));
  const assignedForDate = (board.opshop_pickups || []).filter(
    (pickup) => pickup.pickup_date === pickupDate && currentDriverId(pickup),
  );
  wrapper.append(
    createMetricGrid([
      ["Pickup date", pickupDate, "calendar"],
      ["Assigned pickups", assignedForDate.length, "store"],
      ["Drivers", (board.drivers || []).length, "user"],
    ]),
  );
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-driver-grid workspace-opshop-driver-grid";
  if (!(board.drivers || []).length) {
    grid.append(createEmptyState("No drivers are available for OP SHOP Trip Summary.", "user"));
  } else {
    (board.drivers || []).forEach((driver) => {
      grid.append(createOpShopDriverSummaryCard(
        driver,
        board,
        collections,
        pickupDate,
        state,
        actions,
        onOpenPickupDetail,
      ));
    });
  }
  wrapper.append(grid);
  return wrapper;
}

export function createOpShopTripSummaryToolbar(pickupDate, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-context-panel workspace-context-panel-opshop workspace-opshop-trip-toolbar";
  const heading = createSectionHeading(
    "OP SHOP Trip Summary",
    "Review assigned pickups by driver before generating a Pickup Collection.",
  );
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-opshop-pickup-date-control";
  field.textContent = "Pickup date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = pickupDate;
  input.disabled = state.isOpShopWorkspaceLoading;
  input.addEventListener("change", () => actions.updateOpShopTripSummaryDate(input.value));
  field.append(input);
  panel.append(heading, field);
  return panel;
}

export function createOpShopDriverSummaryCard(
  driver,
  board,
  collections,
  pickupDate,
  state,
  actions,
  onOpenPickupDetail,
) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-driver-card workspace-opshop-driver-card";
  const pickups = assignedOpShopPickupsForDriver(board, pickupDate, driver.driver_id);
  const collection = findPickupCollectionForDriver(
    collections,
    pickupDate,
    driver.driver_id,
  );
  const isLocked = Boolean(collection && ["GENERATED", "SAVED"].includes(collection.status));
  const candidates = readyPickupCollectionCandidates(board, collections);
  const candidate = candidates.find(
    (item) => item.pickup_date === pickupDate && item.driver_id === driver.driver_id,
  );

  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = formatOptional(driver.name, driver.driver_id);
  const badges = document.createElement("div");
  badges.className = "workspace-inline-badges";
  badges.append(createBadge(driver.is_available === false ? "Unavailable" : "Available"));
  if (collection) {
    badges.append(createBadge(collection.status));
  }
  identity.append(heading, badges);
  top.append(identity);

  const counts = pickupCategoryCounts(pickups);
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Regular pickups", counts.regular);
  appendFact(facts, "Oncall pickups", counts.oncall);
  appendFact(facts, "Countryside pickups", counts.countryside);
  appendFact(facts, "Total pickups", pickups.length);
  card.append(top, facts);

  if (isLocked) {
    card.append(createStatus(
      collection.status === "SAVED"
        ? "Saved Pickup Collection locks this driver and pickup date."
        : "Generated Pickup Collection is awaiting confirmation on the Pickup Collections page.",
      "loading",
    ));
  }

  card.append(
    createOpShopPickupGroup("Regular", pickups.filter(isRegularPickup), isLocked, state, actions, onOpenPickupDetail),
    createOpShopPickupGroup("Oncall", pickups.filter(isOncallPickup), isLocked, state, actions, onOpenPickupDetail),
    createOpShopPickupGroup("Countryside", pickups.filter(isCountrysidePickup), isLocked, state, actions, onOpenPickupDetail),
  );

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  if (candidate && !isLocked) {
    const generateButton = createActionButton(
      "Generate Pickup Collection",
      () => actions.generateOpShopPickupCollection({
        ...candidate,
        driver_name: formatOptional(driver.name, driver.driver_id),
      }),
      {
        disabled: isBusy(state, `opshop-generate:${pickupDate}:${driver.driver_id}`),
        primary: true,
      },
    );
    generateButton.dataset.workspaceGenerate = "opshop";
    generateButton.dataset.driverId = driver.driver_id;
    generateButton.dataset.serviceDate = pickupDate;
    actionsRow.append(generateButton);
  }
  card.append(actionsRow);
  return card;
}

export function createOpShopPickupGroup(titleText, pickups, isLocked, state, actions, onOpenPickupDetail) {
  const section = document.createElement("section");
  section.className = "workspace-trip-panel workspace-opshop-trip-group";
  const title = document.createElement("h4");
  title.textContent = `${titleText} (${pickups.length})`;
  section.append(title);
  if (!pickups.length) {
    section.append(createEmptyState(`No ${titleText} pickups assigned`, "store"));
    return section;
  }
  pickups.forEach((pickup) => {
    section.append(createOpShopTripPickupRow(pickup, isLocked, state, actions, onOpenPickupDetail));
  });
  return section;
}

export function createOpShopTripPickupRow(pickup, isLocked, state, actions, onOpenPickupDetail) {
  const row = document.createElement("article");
  row.className = "workspace-record-card workspace-opshop-trip-pickup-row";
  const summary = document.createElement("div");
  summary.className = "workspace-opshop-trip-pickup-summary";
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "workspace-opshop-trip-pickup-trigger";
  trigger.setAttribute("aria-label", `View pickup details for ${formatOptional(pickup.opshop_name)}`);
  const heading = document.createElement("span");
  heading.className = "workspace-opshop-trip-pickup-name";
  heading.textContent = formatOptional(pickup.opshop_name);
  const meta = document.createElement("p");
  meta.className = "workspace-opshop-trip-pickup-meta";
  meta.textContent = [
    formatOptional(pickup.suburb),
    pickupCategoryLabel(pickup),
    isCountrysidePickup(pickup) ? pickup.route_group_name : "",
    pickup.pickup_date,
  ].filter(Boolean).join(" - ");
  trigger.append(heading, meta);
  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onOpenPickupDetail(pickup, trigger);
  });
  const button = createActionButton(
    "Unassign",
    (event) => {
      event.stopPropagation();
      actions.unassignOpShopPickup(pickup.pickup_task_id);
    },
    {
      disabled:
        isLocked
        || pickup.assigned_to_locked
        || isBusy(state, `opshop-unassign:${pickup.pickup_task_id}`),
    },
  );
  summary.append(trigger, button);
  row.append(summary);
  return row;
}
