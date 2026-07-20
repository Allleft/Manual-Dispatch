import { formatOptional } from "../../utils/format-utils.js";
import {
  OPSHOP_COLLECTION_ENTRY_FIELDS,
  getOpShopCollectionEntryValue,
  hasOpShopCollectionEntryDrafts,
} from "../../state/opshop-collection-entry-state.js";

import {
  compareText,
  createActionButton,
  createSectionHeading,
  createBadge,
  createEmptyState,
  isBusy,
} from "./opshop-renderer-utils.js";

export function createCollectionList(collections, state, actions) {
  const exportableCollections = (collections || []).filter(
    (collection) => ["GENERATED", "SAVED"].includes(collection.status),
  );
  const groupedCollections = groupCollectionsByPickupDate(exportableCollections);
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-pickup-collections";
  const intro = document.createElement("section");
  intro.className = "workspace-context-panel workspace-context-panel-opshop workspace-collection-intro";
  intro.append(createSectionHeading(
    "Pickup Collections",
    "Review generated and saved OP SHOP Pickup Collection weight sheets by actual Pickup date.",
  ));
  const pickupDate = state.opshopTripSummaryDate || state.dispatchDate;
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-opshop-pickup-date-control";
  field.textContent = "Pickup date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = pickupDate;
  input.disabled = state.isOpShopWorkspaceLoading;
  input.addEventListener(
    "change",
    () => actions.updateOpShopTripSummaryDate(input.value),
  );
  field.append(input);
  intro.append(field);
  wrapper.append(intro);
  if (!groupedCollections.length) {
    wrapper.append(createEmptyState(
      "No generated or saved Pickup Collections for this Pickup Date.",
      "history",
    ));
    return wrapper;
  }
  groupedCollections.forEach(([pickupDate, dateCollections]) => {
    wrapper.append(createCollectionDateGroup(pickupDate, dateCollections, state, actions));
  });
  return wrapper;
}

export function createCollectionDateGroup(pickupDate, collections, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-opshop workspace-collection-date-group";
  const header = document.createElement("div");
  header.className = "workspace-record-card-top workspace-collection-date-group-header";
  header.append(createSectionHeading(
    `Pickup date: ${pickupDate}`,
    `${collections.length} generated/saved collections for this Pickup Date`,
  ));
  const exportKey = `opshop-export-date:${pickupDate}`;
  const isExporting = isBusy(state, exportKey);
  const hasCollectionMutation = collections.some(
    (collection) => [
      `opshop-entry:${collection.collection_id}`,
      `opshop-save:${collection.collection_id}`,
      `opshop-cancel:${collection.collection_id}`,
      `opshop-export:${collection.collection_id}`,
    ].some((key) => isBusy(state, key)),
  );
  const exportButton = createActionButton(
    isExporting ? "Preparing Daily Export..." : "Export Daily Collections",
    () => actions.exportOpShopPickupCollections(pickupDate),
    {
      disabled: isExporting || hasCollectionMutation || !collections.length,
      primary: true,
    },
  );
  exportButton.title =
    "Exports all generated/saved OP SHOP Pickup Collections for this pickup date, with one sheet per driver.";
  exportButton.dataset.opshopDailyCollectionExport = pickupDate;
  header.append(exportButton);
  section.append(header);
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-collection-grid";
  collections.forEach((collection) => grid.append(createCollectionCard(collection, state, actions)));
  section.append(grid);
  return section;
}

export function createCollectionCard(
  collection,
  state,
  actions,
  { historyMode = false } = {},
) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-collection-card";

  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.className = "workspace-record-kicker";
  kicker.textContent = collection.pickup_date;
  const title = document.createElement("h3");
  title.textContent = formatOptional(collection.driver_name_snapshot, collection.driver_id);
  identity.append(kicker, title);
  top.append(identity, createBadge(collection.status));
  const meta = document.createElement("p");
  meta.className = "workspace-collection-card-meta";
  const metadata = [
    `Workspace date: ${formatOptional(collection.dispatch_date)}`,
    `Pickup date: ${formatOptional(collection.pickup_date)}`,
    `Driver: ${formatOptional(collection.driver_name_snapshot, collection.driver_id)}`,
    `Status: ${formatOptional(collection.status)}`,
  ];
  if (historyMode) {
    metadata.push(
      `Generated: ${formatOptional(collection.generated_at)}`,
      `Saved: ${formatOptional(collection.saved_at)}`,
      `Saved by: ${formatOptional(collection.saved_by_account_name, "Unknown")}`,
    );
  }
  meta.textContent = metadata.join(" | ");

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-collection-actions";
  const collectionBusy = [
    `opshop-entry:${collection.collection_id}`,
    `opshop-save:${collection.collection_id}`,
    `opshop-cancel:${collection.collection_id}`,
    `opshop-export:${collection.collection_id}`,
    `opshop-export-date:${collection.pickup_date}`,
  ].some((key) => isBusy(state, key));
  let weightSheetSaveButton = null;
  if (!historyMode && collection.status === "GENERATED") {
    const entryBusy = isBusy(state, `opshop-entry:${collection.collection_id}`);
    weightSheetSaveButton = createActionButton(
      entryBusy ? "Saving Weight Sheet..." : "Save Weight Sheet",
      () => actions.saveOpShopPickupCollectionWeightSheet(collection.collection_id),
      {
        disabled: collectionBusy
          || !hasOpShopCollectionEntryDrafts(state, collection.collection_id),
        primary: true,
      },
    );
    weightSheetSaveButton.dataset.opshopWeightSheetSave = collection.collection_id;
    actionsRow.append(
      weightSheetSaveButton,
      createActionButton(
        "Save Collection",
        () => actions.saveOpShopPickupCollection(collection.collection_id),
        {
          disabled: collectionBusy,
          primary: true,
        },
      ),
      createActionButton(
        "Cancel Generated",
        () => actions.cancelOpShopPickupCollection(collection.collection_id),
        { disabled: collectionBusy },
      ),
    );
  }
  const isExportable = historyMode
    ? collection.status === "SAVED"
    : ["GENERATED", "SAVED"].includes(collection.status);
  if (isExportable) {
    const isExporting = isBusy(state, `opshop-export:${collection.collection_id}`);
    actionsRow.append(
      createActionButton(
        isExporting ? "Exporting..." : "Export Excel",
        () => actions.exportOpShopPickupCollection(collection.collection_id),
        {
          disabled: collectionBusy,
          primary: historyMode || collection.status === "SAVED",
        },
      ),
    );
  }
  const weightSheet = createCollectionWeightSheetPreview(
    collection,
    state,
    actions,
    {
      readOnly: historyMode || collection.status !== "GENERATED",
      disabled: collectionBusy,
      onDraftChange: () => {
        if (weightSheetSaveButton) {
          weightSheetSaveButton.disabled = false;
        }
      },
    },
  );
  card.append(top, meta, weightSheet, actionsRow);
  return card;
}


export function groupCollectionsByPickupDate(collections) {
  const groups = new Map();
  (collections || []).forEach((collection) => {
    const pickupDate = collection.pickup_date || "Unknown pickup date";
    if (!groups.has(pickupDate)) {
      groups.set(pickupDate, []);
    }
    groups.get(pickupDate).push(collection);
  });
  return Array.from(groups.entries())
    .sort(([leftDate], [rightDate]) => String(rightDate).localeCompare(String(leftDate)))
    .map(([pickupDate, dateCollections]) => [
      pickupDate,
      dateCollections.sort(compareCollectionsForDisplay),
    ]);
}

export function compareCollectionsForDisplay(left, right) {
  const statusOrder = { GENERATED: 0, SAVED: 1 };
  return (statusOrder[left.status] ?? 9) - (statusOrder[right.status] ?? 9)
    || compareText(left.driver_name_snapshot || left.driver_id, right.driver_name_snapshot || right.driver_id)
    || compareText(left.collection_id, right.collection_id);
}

const OPSHOP_COLLECTION_WEIGHT_COLUMNS = [
  "OPSHOP NAME",
  "SUBURB",
  "CLOTHING KG",
  "SHOES KG",
  "TIME IN",
  "TIME OUT",
  "TROLLEYS OUT TO OPSHOPS",
  "TROLLEYS IN TO MCC",
  "HARD TOYS",
  "SOFT TOYS",
  "BLACK BAGS",
  "SHOE BAGS",
];

export function createCollectionWeightSheetPreview(
  collection,
  state,
  actions,
  { readOnly = false, disabled = false, onDraftChange = () => {} } = {},
) {
  const paper = document.createElement("section");
  paper.className = "workspace-opshop-weight-sheet";
  const title = document.createElement("h4");
  title.textContent = "DAILY OP SHOP COLLECTIONS - WEIGHT SHEET";
  const reminder = document.createElement("p");
  reminder.className = "workspace-opshop-weight-sheet-reminder";
  reminder.textContent = "REMINDER : NO BOARD GAMES/ PUZZLES - can not send overseas, don't understand english";
  const toyReminder = document.createElement("p");
  toyReminder.className = "workspace-opshop-weight-sheet-reminder";
  toyReminder.textContent = "**Please ensure HARD & SOFT TOYS are in separate bags**";
  const meta = document.createElement("p");
  meta.className = "workspace-opshop-weight-sheet-meta";
  meta.textContent = `DRIVER NAME: ${formatOptional(collection.driver_name_snapshot, collection.driver_id)}    PICK UP DATE: ${formatDailyCollectionDate(collection.pickup_date)}    DAY: ${formatCollectionDay(collection.pickup_date)}`;
  const rego = document.createElement("p");
  rego.className = "workspace-opshop-weight-sheet-meta";
  rego.textContent = "REGO # ________________________";
  const instruction = document.createElement("p");
  instruction.className = "workspace-opshop-weight-sheet-instruction";
  instruction.textContent = "PLEASE RECORD WEIGHT OF BAGS FOR EACH OP SHOP";

  const tableWrap = document.createElement("div");
  tableWrap.className = "workspace-opshop-weight-sheet-table-wrap";
  tableWrap.tabIndex = 0;
  tableWrap.setAttribute("aria-label", "OP SHOP pickup collection weight sheet table");
  const table = document.createElement("table");
  table.className = "workspace-opshop-weight-sheet-table";
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  OPSHOP_COLLECTION_WEIGHT_COLUMNS.forEach((column) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = column;
    headerRow.append(cell);
  });
  head.append(headerRow);
  const body = document.createElement("tbody");
  (collection.pickups || []).forEach((pickup) => {
    const row = document.createElement("tr");
    const values = collectionWeightSheetRowValues(
      pickup,
      state,
      collection.collection_id,
      !readOnly,
    );
    values.forEach((value, columnIndex) => {
      const cell = document.createElement("td");
      const field = OPSHOP_COLLECTION_ENTRY_FIELDS[columnIndex - 2];
      if (!field || readOnly) {
        cell.textContent = value;
      } else {
        const input = document.createElement("input");
        input.className = "workspace-opshop-weight-sheet-input";
        input.type = field.type;
        input.value = String(value);
        input.disabled = disabled;
        input.setAttribute(
          "aria-label",
          `${OPSHOP_COLLECTION_WEIGHT_COLUMNS[columnIndex]} for ${pickup.opshop_name_snapshot || "OP SHOP"}`,
        );
        if (field.type === "number") {
          input.min = "0";
          input.step = field.step;
          input.inputMode = "decimal";
        }
        input.addEventListener("input", () => {
          if (actions.updateOpShopCollectionEntryDraft(
            collection.collection_id,
            pickup.row_id,
            field.key,
            input.value,
          )) {
            onDraftChange();
          }
        });
        cell.append(input);
      }
      row.append(cell);
    });
    body.append(row);
  });
  table.append(head, body);
  tableWrap.append(table);
  paper.append(title, reminder, toyReminder, meta, rego, instruction, tableWrap);
  return paper;
}

export function collectionWeightSheetRowValues(
  pickup,
  state = {},
  collectionId = "",
  allowDraft = true,
) {
  return [
    formatOptional(pickup.opshop_name_snapshot, ""),
    formatOptional(pickup.suburb_snapshot, ""),
    ...OPSHOP_COLLECTION_ENTRY_FIELDS.map(
      (field) => getOpShopCollectionEntryValue(
        state,
        collectionId,
        pickup,
        field,
        allowDraft,
      ),
    ),
  ];
}


export function formatDailyCollectionDate(value) {
  const [year, month, day] = String(value || "").split("-");
  return year && month && day ? `${day}/${month}/${year}` : "";
}

export function formatCollectionDay(value) {
  const [year, month, day] = String(value || "").split("-");
  if (!year || !month || !day) {
    return "";
  }
  const date = new Date(`${year}-${month}-${day}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleDateString("en-AU", { weekday: "long" }).toUpperCase();
}
