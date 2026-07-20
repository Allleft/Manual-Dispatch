export const OPSHOP_COLLECTION_ENTRY_FIELDS = [
  { key: "clothing_kg", snapshotKey: "clothing_kg_snapshot", type: "number", step: "0.01" },
  { key: "shoes_kg", snapshotKey: "shoes_kg_snapshot", type: "number", step: "0.01" },
  { key: "time_in", snapshotKey: "time_in_snapshot", type: "time" },
  { key: "time_out", snapshotKey: "time_out_snapshot", type: "time" },
  { key: "trolleys_out_to_opshops", snapshotKey: "trolleys_out_to_opshops_snapshot", type: "number", step: "1" },
  { key: "trolleys_in_to_mcc", snapshotKey: "trolleys_in_to_mcc_snapshot", type: "number", step: "1" },
  { key: "hard_toys", snapshotKey: "hard_toys_snapshot", type: "number", step: "1" },
  { key: "soft_toys", snapshotKey: "soft_toys_snapshot", type: "number", step: "1" },
  { key: "black_bags", snapshotKey: "black_bags_snapshot", type: "number", step: "1" },
  { key: "shoe_bags", snapshotKey: "shoe_bags_snapshot", type: "number", step: "1" },
];

export function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object || {}, key);
}

export function getOpShopCollectionEntryValue(
  state,
  collectionId,
  pickup,
  field,
  allowDraft = true,
) {
  const rowDraft = state?.opshopCollectionEntryDrafts?.[collectionId]?.[pickup.row_id];
  if (allowDraft && hasOwn(rowDraft, field.key)) {
    return rowDraft[field.key];
  }
  const persisted = pickup[field.snapshotKey];
  return persisted === null || persisted === undefined ? "" : persisted;
}

export function hasOpShopCollectionEntryDrafts(state, collectionId) {
  const collectionDrafts = state?.opshopCollectionEntryDrafts?.[collectionId];
  return Boolean(collectionDrafts && Object.keys(collectionDrafts).some(
    (rowId) => Object.keys(collectionDrafts[rowId] || {}).length,
  ));
}

export function buildOpShopCollectionEntryRows(state, collection) {
  const collectionId = collection.collection_id;
  const collectionDrafts = state?.opshopCollectionEntryDrafts?.[collectionId] || {};
  const pickupsById = new Map(
    (collection.pickups || []).map((pickup) => [pickup.row_id, pickup]),
  );
  return Object.keys(collectionDrafts).map((rowId) => {
    const pickup = pickupsById.get(rowId);
    if (!pickup) {
      return null;
    }
    const row = { row_id: rowId };
    OPSHOP_COLLECTION_ENTRY_FIELDS.forEach((field) => {
      const value = getOpShopCollectionEntryValue(state, collectionId, pickup, field);
      row[field.key] = field.type === "number" && value !== "" ? Number(value) : value;
    });
    return row;
  }).filter(Boolean);
}
