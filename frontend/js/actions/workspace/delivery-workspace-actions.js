export function createDeliveryWorkspaceActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  function renderDeliveryWorkspacePreservingScroll() {
    if (
      typeof window === "undefined"
      || typeof window.requestAnimationFrame !== "function"
      || typeof window.scrollTo !== "function"
    ) {
      renderWorkspace();
      return;
    }
    const scrollX = Number(window.scrollX || 0);
    const scrollY = Number(window.scrollY || 0);
    renderWorkspace();
    window.requestAnimationFrame(() => window.scrollTo(scrollX, scrollY));
  }

  function currentDeliveryBoard() {
    return state.workspaceRoute === "delivery/trip-summary"
      ? state.deliveryTripSummaryBoard || state.deliveryBoard
      : state.deliveryBoard;
  }

  return {
    renderDeliveryWorkspacePreservingScroll,
    currentDeliveryBoard,
  };
}
