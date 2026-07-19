export function createWorkspaceBusyActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);
  const renderDeliveryWorkspacePreservingScroll = (...args) => context.actions.renderDeliveryWorkspacePreservingScroll(...args);
  const captureMutationContext = (...args) => context.actions.captureMutationContext(...args);
  const nextActionToken = (...args) => context.actions.nextActionToken(...args);
  const isDeliveryMutationCurrent = (...args) => context.actions.isDeliveryMutationCurrent(...args);
  const isOpShopMutationCurrent = (...args) => context.actions.isOpShopMutationCurrent(...args);

  async function runDeliveryAction(
    actionKey,
    callback,
    onError = null,
    { preserveScroll = false } = {},
  ) {
    const context = captureMutationContext();
    const token = nextActionToken();
    state.deliveryBusyActionKeys = state.deliveryBusyActionKeys || {};
    setBusyAction(state.deliveryBusyActionKeys, actionKey, token);
    state.deliveryActionError = "";
    if (preserveScroll) {
      renderDeliveryWorkspacePreservingScroll();
    } else {
      renderWorkspace();
    }
    try {
      await callback(context);
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isDeliveryMutationCurrent(context)) {
        if (typeof onError === "function") {
          onError(error);
        } else {
          state.deliveryActionError = error.message;
        }
      }
    } finally {
      if (clearBusyAction(state.deliveryBusyActionKeys, actionKey, token)) {
        if (!preserveScroll || isDeliveryMutationCurrent(context)) {
          if (preserveScroll) {
            renderDeliveryWorkspacePreservingScroll();
          } else {
            renderWorkspace();
          }
        }
      }
    }
  }

  async function runOpShopAction(actionKey, callback, onError = null) {
    const context = captureMutationContext();
    const token = nextActionToken();
    state.opshopBusyActionKeys = state.opshopBusyActionKeys || {};
    setBusyAction(state.opshopBusyActionKeys, actionKey, token);
    state.opshopActionError = "";
    renderWorkspace();
    try {
      await callback(context);
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isOpShopMutationCurrent(context)) {
        if (typeof onError === "function") {
          await onError(error, context);
        } else {
          state.opshopActionError = error.message;
        }
      }
    } finally {
      if (clearBusyAction(state.opshopBusyActionKeys, actionKey, token)) {
        renderWorkspace();
      }
    }
  }

  function isDeliveryGenerationBusy(confirmation) {
    return Boolean(state.deliveryBusyActionKeys?.[
      `delivery-generate:${confirmation.delivery_date}:${confirmation.driver_id}`
    ]);
  }

  function isOpShopGenerationBusy(confirmation) {
    return Boolean(state.opshopBusyActionKeys?.[
      `opshop-generate:${confirmation.pickup_date}:${confirmation.driver_id}`
    ]);
  }

  function restoreGenerateButtonFocus(workspace, confirmation) {
    if (
      typeof document === "undefined"
      || typeof window === "undefined"
      || typeof window.requestAnimationFrame !== "function"
    ) {
      return;
    }
    window.requestAnimationFrame(() => {
      const button = Array.from(
        document.querySelectorAll(`[data-workspace-generate="${workspace}"]`),
      ).find(
        (item) =>
          item.dataset.driverId === confirmation.driver_id
          && item.dataset.serviceDate === (
            confirmation.delivery_date || confirmation.pickup_date
          ),
      );
      button?.focus();
    });
  }

  function setBusyAction(registry, actionKey, token) {
    registry[actionKey] = token;
  }

  function clearBusyAction(registry, actionKey, token) {
    if (!registry || registry[actionKey] !== token) {
      return false;
    }
    delete registry[actionKey];
    return true;
  }

  return {
    runDeliveryAction,
    runOpShopAction,
    isDeliveryGenerationBusy,
    isOpShopGenerationBusy,
    restoreGenerateButtonFocus,
    setBusyAction,
    clearBusyAction,
  };
}
