export function syncScopedOpShopModalState(state) {
  if (state.activeWorkspace !== "opshop" || !state.opshopBoard) {
    return false;
  }

  const pickups = state.opshopBoard.opshop_pickups || [];
  state.scheduledOpShopPickups = pickups.filter(
    (pickup) => pickup.run_type === "REGULAR",
  );
  state.oncallOpShopPickups = pickups.filter(
    (pickup) =>
      pickup.run_type === "ON_CALL" && pickup.pickup_category !== "COUNTRYSIDE",
  );
  state.countrysideOpShopPickups = pickups.filter(
    (pickup) => pickup.pickup_category === "COUNTRYSIDE",
  );
  state.countrysideRouteGroups = state.opshopBoard.countryside_route_groups || [];

  const regularDates = state.scheduledOpShopPickups
    .map((pickup) => pickup.pickup_date)
    .filter(Boolean)
    .sort();
  state.opshopRegularListWindowStart = regularDates[0] || state.dispatchDate;
  state.opshopRegularListWindowEnd = regularDates.at(-1) || state.dispatchDate;
  return true;
}

export function getOpShopModalDrivers(state) {
  if (state.activeWorkspace === "opshop") {
    return state.opshopBoard?.drivers || [];
  }
  return state.drivers;
}
