const UNASSIGNED_ROUTE_GROUP_KEY = "__unassigned_route_group__";


export function getCountrysidePickupRouteGroupCollapseKey(pickupDate, routeGroupId) {
  return JSON.stringify([
    String(pickupDate || ""),
    String(routeGroupId || UNASSIGNED_ROUTE_GROUP_KEY),
  ]);
}


export function getCountrysidePickupRouteGroupPanelId(pickupDate, routeGroupId) {
  return [
    "workspace-countryside-route-group",
    encodeURIComponent(String(pickupDate || "no-date")),
    encodeURIComponent(String(routeGroupId || UNASSIGNED_ROUTE_GROUP_KEY)),
  ].join("-");
}


export function getCountrysideTemplateRouteGroupPanelId(routeGroupId) {
  return `opshop-countryside-template-route-${encodeURIComponent(
    String(routeGroupId || UNASSIGNED_ROUTE_GROUP_KEY),
  )}`;
}
