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
    await runOpShopAction(`opshop-save:${collectionId}`, async (context) => {
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
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function exportOpShopPickupCollection(collectionId) {
    await runOpShopAction(`opshop-export:${collectionId}`, async () => {
      await api.exportOpShopPickupCollectionExcel(collectionId);
    });
  }

  async function exportOpShopPickupCollections(pickupDate) {
    const scopedDate = pickupDate || state.opshopTripSummaryDate || state.dispatchDate;
    const actionKey = `opshop-export-date:${scopedDate}`;
    if (state.opshopBusyActionKeys?.[actionKey]) {
      return;
    }
    await runOpShopAction(actionKey, async () => {
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
    cancelOpShopPickupCollection,
    exportOpShopPickupCollection,
    exportOpShopPickupCollections,
  };
}
