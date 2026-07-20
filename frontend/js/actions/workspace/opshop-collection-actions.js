import {
  OPSHOP_COLLECTION_ENTRY_FIELDS,
  buildOpShopCollectionEntryRows,
  hasOpShopCollectionEntryDrafts,
} from "../../state/opshop-collection-entry-state.js";


export function createOpShopCollectionActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadOpShopRoute = (...args) => context.actions.loadOpShopRoute(...args);
  const runOpShopAction = (...args) => context.actions.runOpShopAction(...args);
  const saveSnapshotPayload = (...args) => context.actions.saveSnapshotPayload(...args);
  const isOpShopGenerationBusy = (...args) => context.actions.isOpShopGenerationBusy(...args);
  const restoreGenerateButtonFocus = (...args) => context.actions.restoreGenerateButtonFocus(...args);
  const isOpShopMutationCurrent = (...args) => context.actions.isOpShopMutationCurrent(...args);


  function findCollection(collectionId) {
    return (state.opshopPickupCollections || []).find(
      (collection) => collection.collection_id === collectionId,
    ) || (state.opshopSavedHistoryCollections || []).find(
      (collection) => collection.collection_id === collectionId,
    ) || null;
  }

  function isCollectionMutationBusy(collection) {
    if (!collection) {
      return false;
    }
    const keys = [
      `opshop-entry:${collection.collection_id}`,
      `opshop-save:${collection.collection_id}`,
      `opshop-cancel:${collection.collection_id}`,
      `opshop-export:${collection.collection_id}`,
      `opshop-export-date:${collection.pickup_date}`,
    ];
    return keys.some((key) => Boolean(state.opshopBusyActionKeys?.[key]));
  }

  function updateOpShopCollectionEntryDraft(collectionId, rowId, fieldKey, value) {
    const collection = findCollection(collectionId);
    if (
      !collection
      || collection.status !== "GENERATED"
      || !(collection.pickups || []).some((pickup) => pickup.row_id === rowId)
      || !OPSHOP_COLLECTION_ENTRY_FIELDS.some((field) => field.key === fieldKey)
    ) {
      return false;
    }
    state.opshopCollectionEntryDrafts = state.opshopCollectionEntryDrafts || {};
    state.opshopCollectionEntryDraftVersions =
      state.opshopCollectionEntryDraftVersions || {};
    state.opshopCollectionEntryDrafts[collectionId] =
      state.opshopCollectionEntryDrafts[collectionId] || {};
    state.opshopCollectionEntryDrafts[collectionId][rowId] =
      state.opshopCollectionEntryDrafts[collectionId][rowId] || {};
    state.opshopCollectionEntryDrafts[collectionId][rowId][fieldKey] = value;
    state.opshopCollectionEntryDraftVersions[collectionId] =
      (state.opshopCollectionEntryDraftVersions[collectionId] || 0) + 1;
    return true;
  }

  async function flushOpShopCollectionEntryDrafts(collectionId, mutationContext) {
    const collection = findCollection(collectionId);
    if (
      !collection
      || collection.status !== "GENERATED"
      || !hasOpShopCollectionEntryDrafts(state, collectionId)
    ) {
      return collection;
    }
    const rows = buildOpShopCollectionEntryRows(state, collection);
    if (!rows.length) {
      return collection;
    }
    const draftVersion = state.opshopCollectionEntryDraftVersions?.[collectionId] || 0;
    const updated = await api.updateOpShopPickupCollectionRows(collectionId, { rows });
    if (!mutationContext || isOpShopMutationCurrent(mutationContext)) {
      state.opshopPickupCollections = (state.opshopPickupCollections || []).map(
        (item) => item.collection_id === collectionId ? updated : item,
      );
    }
    if (
      (state.opshopCollectionEntryDraftVersions?.[collectionId] || 0)
      === draftVersion
    ) {
      delete state.opshopCollectionEntryDrafts[collectionId];
      delete state.opshopCollectionEntryDraftVersions[collectionId];
    }
    return updated;
  }

  async function saveOpShopPickupCollectionWeightSheet(collectionId) {
    const collection = findCollection(collectionId);
    if (
      !collection
      || isCollectionMutationBusy(collection)
      || !hasOpShopCollectionEntryDrafts(state, collectionId)
    ) {
      return;
    }
    await runOpShopAction(`opshop-entry:${collectionId}`, async (context) => {
      await flushOpShopCollectionEntryDrafts(collectionId, context);
    });
  }

  function generateOpShopPickupCollection(candidate) {
    if (!candidate || !(candidate.pickups || []).length) {
      return;
    }
    state.opshopGenerationConfirmation = {
      ...candidate,
      dispatch_date: state.dispatchDate,
      error: "",
      pickups: (candidate.pickups || []).map((pickup) => ({ ...pickup })),
    };
    state.opshopActionError = "";
    renderWorkspace();
  }

  function closeOpShopGenerationConfirmation() {
    const confirmation = state.opshopGenerationConfirmation;
    if (!confirmation || isOpShopGenerationBusy(confirmation)) {
      return;
    }
    state.opshopGenerationConfirmation = null;
    renderWorkspace();
    restoreGenerateButtonFocus("opshop", confirmation);
  }

  async function confirmGenerateOpShopPickupCollection() {
    const candidate = state.opshopGenerationConfirmation;
    if (!candidate || isOpShopGenerationBusy(candidate)) {
      return;
    }
    await runOpShopAction(
      `opshop-generate:${candidate.pickup_date}:${candidate.driver_id}`,
      async (context) => {
        await api.createGeneratedOpShopPickupCollection({
          pickup_date: candidate.pickup_date,
          driver_id: candidate.driver_id,
        });
        if (isOpShopMutationCurrent(context)) {
          state.opshopGenerationConfirmation = null;
          await loadOpShopRoute(context.route);
        }
      },
      async (error, context) => {
        await loadOpShopRoute(context.route);
        if (isOpShopMutationCurrent(context)) {
          state.opshopGenerationConfirmation = {
            ...candidate,
            error: error.message,
          };
        }
      },
    );
  }

  async function saveOpShopPickupCollection(collectionId) {
    const collection = findCollection(collectionId);
    if (!collection || isCollectionMutationBusy(collection)) {
      return;
    }
    await runOpShopAction(`opshop-save:${collectionId}`, async (context) => {
      await flushOpShopCollectionEntryDrafts(collectionId, context);
      await api.saveGeneratedOpShopPickupCollection(
        collectionId,
        saveSnapshotPayload(),
      );
      if (isOpShopMutationCurrent(context)) {
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function cancelOpShopPickupCollection(collectionId) {
    const confirmed = confirmAction(
      "Cancel this generated OP SHOP Pickup Collection? Captured pickups will return to the OP SHOP workspace.",
    );
    if (!confirmed) {
      return;
    }
    await runOpShopAction(`opshop-cancel:${collectionId}`, async (context) => {
      await api.cancelGeneratedOpShopPickupCollection(collectionId);
      if (isOpShopMutationCurrent(context)) {
        delete state.opshopCollectionEntryDrafts?.[collectionId];
        delete state.opshopCollectionEntryDraftVersions?.[collectionId];
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function exportOpShopPickupCollection(collectionId) {
    const collection = findCollection(collectionId);
    if (!collection || isCollectionMutationBusy(collection)) {
      return;
    }
    await runOpShopAction(`opshop-export:${collectionId}`, async (context) => {
      await flushOpShopCollectionEntryDrafts(collectionId, context);
      await api.exportOpShopPickupCollectionExcel(collectionId);
    });
  }

  async function exportOpShopPickupCollections(pickupDate) {
    const scopedDate = pickupDate || state.opshopTripSummaryDate || state.dispatchDate;
    const actionKey = `opshop-export-date:${scopedDate}`;
    if (state.opshopBusyActionKeys?.[actionKey]) {
      return;
    }
    const collections = (state.opshopPickupCollections || []).filter(
      (collection) => collection.pickup_date === scopedDate,
    );
    if (collections.some(isCollectionMutationBusy)) {
      return;
    }
    await runOpShopAction(actionKey, async (context) => {
      for (const collection of collections) {
        if (
          collection.status === "GENERATED"
          && hasOpShopCollectionEntryDrafts(state, collection.collection_id)
        ) {
          await flushOpShopCollectionEntryDrafts(collection.collection_id, context);
        }
      }
      await api.exportOpShopPickupCollectionsExcel({
        pickupDate: scopedDate,
      });
    });
  }

  return {
    generateOpShopPickupCollection,
    closeOpShopGenerationConfirmation,
    confirmGenerateOpShopPickupCollection,
    saveOpShopPickupCollection,
    saveOpShopPickupCollectionWeightSheet,
    updateOpShopCollectionEntryDraft,
    cancelOpShopPickupCollection,
    exportOpShopPickupCollection,
    exportOpShopPickupCollections,
  };
}
