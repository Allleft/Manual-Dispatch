export function initializeCollapsedPickupDateGroups(pickups, dispatchDate) {
  const collapsedDates = {};
  pickups.forEach((pickup) => {
    const pickupDate = pickup.pickup_date || "";
    if (pickupDate && !(pickupDate in collapsedDates)) {
      collapsedDates[pickupDate] = isPickupDateBeforeDispatch(pickupDate, dispatchDate);
    }
  });
  return collapsedDates;
}


export function getDateGroupCollapsed(collapsedDates, pickupDate, dispatchDate) {
  if (Object.prototype.hasOwnProperty.call(collapsedDates, pickupDate)) {
    return Boolean(collapsedDates[pickupDate]);
  }
  return isPickupDateBeforeDispatch(pickupDate, dispatchDate);
}


export function toggleCollapsedPickupDateGroup(collapsedDates, pickupDate, dispatchDate) {
  return {
    ...collapsedDates,
    [pickupDate]: !getDateGroupCollapsed(collapsedDates, pickupDate, dispatchDate),
  };
}


export function getDateGroupListId(prefix, pickupDate) {
  const safeDate = String(pickupDate || "no-date").replace(/[^a-zA-Z0-9_-]/g, "-");
  return `${prefix}-opshop-date-card-list-${safeDate}`;
}


function isPickupDateBeforeDispatch(pickupDate, dispatchDate) {
  return Boolean(pickupDate && dispatchDate && String(pickupDate) < String(dispatchDate));
}
