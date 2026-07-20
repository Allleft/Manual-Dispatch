import {
  OPSHOP_COLLECTION_ENTRY_FIELDS,
  buildOpShopCollectionEntryRows,
  hasOpShopCollectionEntryDrafts,
} from "../../state/opshop-collection-entry-state.js";

const COLLECTION_ENTRY_FLUSH_STATUS = Object.freeze({
  NO_DRAFT: "NO_DRAFT",
  FLUSHED_STABLE: "FLUSHED_STABLE",
  NEWER_DRAFT: "NEWER_DRAFT",
  STALE_CONTEXT: "STALE_CONTEXT",
});


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
      return {
        collection,
        status: COLLECTION_ENTRY_FLUSH_STATUS.NO_DRAFT,
      };
    }
    const submittedDraftVersion =
      state.opshopCollectionEntryDraftVersions?.[collectionId] || 0;
    const rows = buildOpShopCollectionEntryRows(state, collection);
    if (!rows.length) {
      return {
        collection,
        status: COLLECTION_ENTRY_FLUSH_STATUS.NEWER_DRAFT,
        submittedDraftVersion,
        currentDraftVersion:
          state.opshopCollectionEntryDraftVersions?.[collectionId] || 0,
      };
    }
    const updated = await api.updateOpShopPickupCollectionRows(collectionId, { rows });
    const mutationIsCurrent =
      !mutationContext || isOpShopMutationCurrent(mutationContext);
    if (!mutationIsCurrent) {
      return {
        collection: updated,
        status: COLLECTION_ENTRY_FLUSH_STATUS.STALE_CONTEXT,
        submittedDraftVersion,
      };
    }
    state.opshopPickupCollections = (state.opshopPickupCollections || []).map(
      (item) => item.collection_id === collectionId ? updated : item,
    );
    const currentDraftVersion =
      state.opshopCollectionEntryDraftVersions?.[collectionId] || 0;
    if (currentDraftVersion !== submittedDraftVersion) {
      return {
        collection: updated,
        status: COLLECTION_ENTRY_FLUSH_STATUS.NEWER_DRAFT,
        submittedDraftVersion,
        currentDraftVersion,
      };
    }
    delete state.opshopCollectionEntryDrafts[collectionId];
    delete state.opshopCollectionEntryDraftVersions[collectionId];
    return {
      collection: updated,
      status: COLLECTION_ENTRY_FLUSH_STATUS.FLUSHED_STABLE,
      submittedDraftVersion,
    };
  }

  function canContinueAfterCollectionEntryFlush(
    result,
    mutationContext,
    collectionIds,
    newerDraftMessage,
  ) {
    if (
      !isOpShopMutationCurrent(mutationContext)
      || result.status === COLLECTION_ENTRY_FLUSH_STATUS.STALE_CONTEXT
    ) {
      return false;
    }
    const dirtyDraftRemains = collectionIds.some(
      (collectionId) => hasOpShopCollectionEntryDrafts(state, collectionId),
    );
    if (
      result.status === COLLECTION_ENTRY_FLUSH_STATUS.NEWER_DRAFT
      || dirtyDraftRemains
    ) {
      state.opshopActionError = newerDraftMessage;
      return false;
    }
    return (
      result.status === COLLECTION_ENTRY_FLUSH_STATUS.NO_DRAFT
      || result.status === COLLECTION_ENTRY_FLUSH_STATUS.FLUSHED_STABLE
    );
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
      const result = await flushOpShopCollectionEntryDrafts(collectionId, context);
      if (
        isOpShopMutationCurrent(context)
        && result.status === COLLECTION_ENTRY_FLUSH_STATUS.NEWER_DRAFT
      ) {
        state.opshopActionError =
          "Newer Weight Sheet changes remain unsaved. Save again to persist the latest values.";
      }
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
      const result = await flushOpShopCollectionEntryDrafts(collectionId, context);
      if (!canContinueAfterCollectionEntryFlush(
        result,
        context,
        [collectionId],
        "Weight Sheet changed while saving. Review the latest entries and try Save Collection again.",
      )) {
        return;
      }
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
      const result = await flushOpShopCollectionEntryDrafts(collectionId, context);
      if (!canContinueAfterCollectionEntryFlush(
        result,
        context,
        [collectionId],
        "Weight Sheet changed while exporting. Review the latest entries and try Export again.",
      )) {
        return;
      }
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
        if (!isOpShopMutationCurrent(context)) {
          return;
        }
        if (
          collection.status === "GENERATED"
          && hasOpShopCollectionEntryDrafts(state, collection.collection_id)
        ) {
          const result = await flushOpShopCollectionEntryDrafts(
            collection.collection_id,
            context,
          );
          if (!canContinueAfterCollectionEntryFlush(
            result,
            context,
            [collection.collection_id],
            "A Weight Sheet changed while preparing the Daily Export. Review the latest entries and try again.",
          )) {
            return;
          }
        }
      }
      const generatedCollectionIds = (state.opshopPickupCollections || [])
        .filter(
          (collection) =>
            collection.pickup_date === scopedDate
            && collection.status === "GENERATED",
        )
        .map((collection) => collection.collection_id);
      if (!canContinueAfterCollectionEntryFlush(
        { status: COLLECTION_ENTRY_FLUSH_STATUS.NO_DRAFT },
        context,
        generatedCollectionIds,
        "A Weight Sheet changed while preparing the Daily Export. Review the latest entries and try again.",
      )) {
        return;
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
