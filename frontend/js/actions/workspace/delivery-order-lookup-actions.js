import { defaultDeliveryOrderLookupState } from "../../state/delivery-order-lookup-state.js";

export function createDeliveryOrderLookupActions({ api, state, renderWorkspace }) {
  function renderLookup() {
    const position = typeof window !== "undefined" ? [window.scrollX, window.scrollY] : null;
    renderWorkspace();
    if (position && typeof window.scrollTo === "function") {
      window.scrollTo(...position);
    }
  }

  function openDeliveryOrderLookup() {
    state.deliveryOrderLookup = { ...defaultDeliveryOrderLookupState(), open: true };
    renderLookup();
  }

  function closeDeliveryOrderLookup() {
    state.deliveryOrderLookup = defaultDeliveryOrderLookupState();
    renderLookup();
    if (typeof window !== "undefined") {
      window.setTimeout(() => document.querySelector("[data-find-delivery-invoice]")?.focus(), 0);
    }
  }

  function updateDeliveryOrderLookupQuery(value) {
    const lookup = state.deliveryOrderLookup;
    lookup.query = value;
    lookup.requestVersion += 1;
    lookup.loading = false;
    lookup.result = null;
    lookup.error = "";
  }

  async function searchDeliveryOrderLookup() {
    const lookup = state.deliveryOrderLookup;
    if (!lookup?.open || lookup.loading || !state.isLoggedIn) return;
    const query = lookup.query.trim();
    if (!query) return;
    const version = ++lookup.requestVersion;
    const session = state.authSessionVersion;
    const isCurrent = () => state.isLoggedIn && state.authSessionVersion === session
      && state.deliveryOrderLookup === lookup && lookup.open
      && lookup.requestVersion === version && lookup.query.trim() === query;
    lookup.loading = true;
    lookup.error = "";
    lookup.result = null;
    renderLookup();
    try {
      const result = await api.lookupDeliveryOrdersByInvoice(query);
      if (isCurrent()) lookup.result = result;
    } catch (error) {
      if (isCurrent()) lookup.error = `Unable to find Delivery Order. ${error.message}`;
    } finally {
      if (isCurrent()) {
        lookup.loading = false;
        renderLookup();
      }
    }
  }

  return { openDeliveryOrderLookup, closeDeliveryOrderLookup,
    updateDeliveryOrderLookupQuery, searchDeliveryOrderLookup };
}
