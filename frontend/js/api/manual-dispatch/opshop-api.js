import {
  getApiUrl,
  requestBlobDownload,
  requestJson,
  requestResponse,
} from "./shared-api.js";


export async function apiGetOpShopWorkspaceBoard(dispatchDate) {
  return requestJson("/api/manual-dispatch/opshop/board", {
    query: { dispatch_date: dispatchDate },
  });
}

export async function apiGetOpShopTripSummary({ pickupDate }) {
  return requestJson("/api/manual-dispatch/opshop/trip-summary", {
    query: { pickup_date: pickupDate },
  });
}

export async function apiListOpShopPickupCollections(dispatchDate, status = "") {
  return requestJson("/api/manual-dispatch/opshop/pickup-collections", {
    query: { dispatch_date: dispatchDate, status },
  });
}

export async function apiListOpShopPickupCollectionsByPickupDate(pickupDate, status = "") {
  return requestJson("/api/manual-dispatch/opshop/pickup-collections", {
    query: { pickup_date: pickupDate, status },
  });
}

export async function apiListOpShopPickupCollectionsByDispatchAndPickupDate(
  dispatchDate,
  pickupDate,
  status = "",
) {
  return requestJson("/api/manual-dispatch/opshop/pickup-collections", {
    query: { dispatch_date: dispatchDate, pickup_date: pickupDate, status },
  });
}

export async function apiApplyOpShopWorkspaceAssignments(payload) {
  return requestJson("/api/manual-dispatch/opshop/pickups/assignments/apply", {
    method: "POST",
    body: payload,
  });
}

export async function apiUnassignOpShopWorkspacePickup(payload) {
  return requestJson("/api/manual-dispatch/opshop/pickups/assignments/unassign", {
    method: "POST",
    body: payload,
  });
}

export async function apiAssignOpShopWorkspaceCountrysideRouteGroup(
  routeGroupId,
  payload,
) {
  return requestJson(
    `/api/manual-dispatch/opshop/countryside-route-groups/${encodeURIComponent(routeGroupId)}/assign`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function apiCreateGeneratedOpShopPickupCollection(payload) {
  return requestJson("/api/manual-dispatch/opshop/pickup-collections/generated", {
    method: "POST",
    body: payload,
  });
}

export async function apiUpdateOpShopPickupCollectionRows(collectionId, payload) {
  return requestJson(
    `/api/manual-dispatch/opshop/pickup-collections/${encodeURIComponent(collectionId)}/rows`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}


export async function apiSaveGeneratedOpShopPickupCollection(collectionId, payload) {
  return requestJson(
    `/api/manual-dispatch/opshop/pickup-collections/${encodeURIComponent(collectionId)}/save`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function apiCancelGeneratedOpShopPickupCollection(collectionId) {
  return requestJson(
    `/api/manual-dispatch/opshop/pickup-collections/${encodeURIComponent(collectionId)}/cancel-generated`,
    { method: "POST" },
  );
}

export async function apiExportOpShopPickupCollectionExcel(collectionId) {
  return requestBlobDownload(
    `/api/manual-dispatch/opshop/pickup-collections/${encodeURIComponent(collectionId)}/export-excel`,
    "opshop-pickup-collection.xlsx",
  );
}

export async function apiExportOpShopPickupCollectionsExcel({
  pickupDate,
  status = "",
}) {
  const query = new URLSearchParams();
  query.set("pickup_date", pickupDate);
  if (status) {
    query.set("status", status);
  }
  return requestBlobDownload(
    `/api/manual-dispatch/opshop/pickup-collections/export-excel?${query.toString()}`,
    `Daily_OPSHOP_Collections_${pickupDate}.xlsx`,
  );
}

export async function apiListOpShopPickupSchedules() {
  return requestJson("/api/manual-dispatch/opshop-pickup-schedules", {
    query: { run_type: "scheduled" },
  });
}

export async function apiListOncallOpShopPickupSchedules() {
  return requestJson("/api/manual-dispatch/opshop-pickup-schedules", {
    query: { run_type: "oncall" },
  });
}

export async function apiListCountrysideOpShopPickupSchedules() {
  return requestJson("/api/manual-dispatch/opshop-pickup-schedules", {
    query: { pickup_category: "COUNTRYSIDE" },
  });
}

export async function apiListCountrysideRouteGroups() {
  return requestJson("/api/manual-dispatch/opshop-countryside-route-groups");
}

export async function apiCreateCountrysideRouteGroup(payload) {
  return requestJson("/api/manual-dispatch/opshop-countryside-route-groups", {
    method: "POST",
    body: payload,
  });
}

export async function apiUpdateCountrysideRouteGroup(routeGroupId, payload) {
  return requestJson(
    `/api/manual-dispatch/opshop-countryside-route-groups/${encodeURIComponent(routeGroupId)}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function apiDisableCountrysideRouteGroup(routeGroupId) {
  return requestJson(
    `/api/manual-dispatch/opshop-countryside-route-groups/${encodeURIComponent(routeGroupId)}/disable`,
    { method: "POST" },
  );
}

export async function apiListCountrysideRouteMemberships(routeGroupId) {
  return requestJson(
    `/api/manual-dispatch/opshop-countryside-route-groups/${encodeURIComponent(routeGroupId)}/memberships`,
  );
}

export async function apiAddCountrysideRouteMembership(routeGroupId, payload) {
  return requestJson(
    `/api/manual-dispatch/opshop-countryside-route-groups/${encodeURIComponent(routeGroupId)}/memberships`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function apiRemoveCountrysideRouteMembership(scheduleId) {
  return requestJson(
    `/api/manual-dispatch/opshop-countryside-memberships/${encodeURIComponent(scheduleId)}/remove`,
    { method: "POST" },
  );
}

export async function apiMoveCountrysideRouteMembership(scheduleId, payload) {
  return requestJson(
    `/api/manual-dispatch/opshop-countryside-memberships/${encodeURIComponent(scheduleId)}/move`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function apiListOpShopTemplates(runType, includeInactive = false) {
  return requestJson("/api/manual-dispatch/opshop-templates", {
    query: { run_type: runType, include_inactive: includeInactive },
  });
}

export async function apiCreateOpShopTemplate(payload) {
  return requestJson("/api/manual-dispatch/opshop-templates", {
    method: "POST",
    body: payload,
  });
}

export async function apiUpdateOpShopTemplate(scheduleId, payload) {
  return requestJson(`/api/manual-dispatch/opshop-templates/${encodeURIComponent(scheduleId)}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function apiDisableOpShopTemplate(scheduleId) {
  return requestJson(
    `/api/manual-dispatch/opshop-templates/${encodeURIComponent(scheduleId)}/disable`,
    { method: "POST" },
  );
}

export async function apiCreateOpShopPickup(payload) {
  return requestJson("/api/manual-dispatch/opshop-pickups", {
    method: "POST",
    body: payload,
  });
}

export async function apiCreateOncallOpShopPickup(payload) {
  return requestJson("/api/manual-dispatch/opshop-pickups/oncall", {
    method: "POST",
    body: payload,
  });
}

export async function apiUpdateOpShopPickup(pickupTaskId, payload) {
  return requestJson(`/api/manual-dispatch/opshop-pickups/${encodeURIComponent(pickupTaskId)}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function apiDeleteOpShopPickup(pickupTaskId) {
  return requestJson(`/api/manual-dispatch/opshop-pickups/${encodeURIComponent(pickupTaskId)}`, {
    method: "DELETE",
  });
}

export async function apiApplyWeeklyOpShopPickupAssignments(payload) {
  return requestJson("/api/manual-dispatch/opshop-pickups/weekly-assignments/apply", {
    method: "POST",
    body: payload,
  });
}

export async function apiApplyOncallOpShopPickupAssignments(payload) {
  return requestJson("/api/manual-dispatch/opshop-pickups/oncall-assignments/apply", {
    method: "POST",
    body: payload,
  });
}

export async function apiApplyCountrysideOpShopPickupAssignments(payload) {
  return requestJson("/api/manual-dispatch/opshop-pickups/countryside-assignments/apply", {
    method: "POST",
    body: payload,
  });
}

export async function apiAssignCountrysideRouteGroup(routeGroupId, payload) {
  return requestJson(
    `/api/manual-dispatch/opshop-pickups/countryside-route-groups/${encodeURIComponent(routeGroupId)}/assign`,
    {
      method: "POST",
      body: payload,
    },
  );
}

export function getOpShopPickupRunSheetExcelExportUrl(dispatchDate) {
  return getApiUrl("/api/manual-dispatch/opshop-pickups/export-excel", {
    dispatch_date: dispatchDate,
  });
}

export function apiExportOpShopPickupRunSheetExcel(dispatchDate) {
  return requestResponse("/api/manual-dispatch/opshop-pickups/export-excel", {
    query: { dispatch_date: dispatchDate },
  });
}
