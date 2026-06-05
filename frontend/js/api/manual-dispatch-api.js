const API_BASE_URL =
  window.MANUAL_DISPATCH_API_BASE_URL ||
  (window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "");


function getApiUrl(path, query = {}) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const baseUrl = API_BASE_URL ? API_BASE_URL.replace(/\/$/, "") : window.location.origin;
  const url = new URL(`${baseUrl}${normalizedPath}`);
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}


export function formatApiErrorDetail(detail) {
  if (!detail) {
    return "";
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (item && typeof item === "object") {
          const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
          const message = item.msg || JSON.stringify(item);
          return location ? `${location}: ${message}` : message;
        }
        return String(item);
      })
      .join("; ");
  }

  if (typeof detail === "object") {
    return detail.message || detail.msg || JSON.stringify(detail);
  }

  return String(detail);
}


async function requestJson(path, options = {}) {
  const response = await fetch(getApiUrl(path, options.query), {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = formatApiErrorDetail(payload.detail) || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return response.json();
}


export async function apiGetBoard(dispatchDate) {
  return requestJson("/api/manual-dispatch/board", {
    query: { dispatch_date: dispatchDate },
  });
}


export async function apiAssignTask(payload) {
  return requestJson("/api/manual-dispatch/assign", {
    method: "POST",
    body: payload,
  });
}


export async function apiUnassignTask(payload) {
  return requestJson("/api/manual-dispatch/unassign", {
    method: "POST",
    body: payload,
  });
}


export async function apiAssignDriverVehicle(payload) {
  return requestJson("/api/manual-dispatch/driver-vehicle", {
    method: "POST",
    body: payload,
  });
}


export async function apiRegisterAccount(payload) {
  return requestJson("/api/manual-dispatch/auth/register", {
    method: "POST",
    body: payload,
  });
}


export async function apiLoginAccount(payload) {
  return requestJson("/api/manual-dispatch/auth/login", {
    method: "POST",
    body: payload,
  });
}


export async function apiResetPassword(payload) {
  return requestJson("/api/manual-dispatch/auth/reset-password", {
    method: "POST",
    body: payload,
  });
}


export async function apiCreateOrder(payload) {
  return requestJson("/api/manual-dispatch/orders", {
    method: "POST",
    body: payload,
  });
}


export async function apiUpdateOrder(orderId, payload) {
  return requestJson(`/api/manual-dispatch/orders/${encodeURIComponent(orderId)}`, {
    method: "PATCH",
    body: payload,
  });
}


export async function apiCancelOrder(orderId) {
  return requestJson(`/api/manual-dispatch/orders/${encodeURIComponent(orderId)}/cancel`, {
    method: "POST",
  });
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
  return fetch(getOpShopPickupRunSheetExcelExportUrl(dispatchDate));
}


export async function apiSaveFinalSummary(payload) {
  return requestJson("/api/manual-dispatch/final-summaries", {
    method: "POST",
    body: payload,
  });
}


export async function apiCreateGeneratedFinalSummary(payload) {
  return requestJson("/api/manual-dispatch/final-summaries/generated", {
    method: "POST",
    body: payload,
  });
}


export async function apiSaveGeneratedFinalSummary(summaryId, payload) {
  return requestJson(`/api/manual-dispatch/final-summaries/${encodeURIComponent(summaryId)}/save`, {
    method: "POST",
    body: payload,
  });
}


export async function apiCancelGeneratedFinalSummary(summaryId) {
  return requestJson(
    `/api/manual-dispatch/final-summaries/${encodeURIComponent(summaryId)}/cancel-generated`,
    { method: "POST" },
  );
}


export async function apiListFinalSummaries(dispatchDate, deliveryDate) {
  return requestJson("/api/manual-dispatch/final-summaries", {
    query: { dispatch_date: dispatchDate, delivery_date: deliveryDate },
  });
}


export async function apiListFinalSummaryDates() {
  return requestJson("/api/manual-dispatch/final-summary-dates");
}


export async function apiGetSpecifications() {
  return requestJson("/api/manual-dispatch/specifications");
}


export async function apiCreateDriver(payload) {
  return requestJson("/api/manual-dispatch/drivers", {
    method: "POST",
    body: payload,
  });
}


export async function apiUpdateDriver(driverId, payload) {
  return requestJson(`/api/manual-dispatch/drivers/${encodeURIComponent(driverId)}`, {
    method: "PATCH",
    body: payload,
  });
}


export async function apiDeleteDriver(driverId) {
  return requestJson(`/api/manual-dispatch/drivers/${encodeURIComponent(driverId)}`, {
    method: "DELETE",
  });
}


export async function apiCreateVehicle(payload) {
  return requestJson("/api/manual-dispatch/vehicles", {
    method: "POST",
    body: payload,
  });
}


export async function apiUpdateVehicle(vehicleId, payload) {
  return requestJson(`/api/manual-dispatch/vehicles/${encodeURIComponent(vehicleId)}`, {
    method: "PATCH",
    body: payload,
  });
}


export async function apiDeleteVehicle(vehicleId) {
  return requestJson(`/api/manual-dispatch/vehicles/${encodeURIComponent(vehicleId)}`, {
    method: "DELETE",
  });
}


export function getFinalSummaryExcelExportUrl(dispatchDate, deliveryDate) {
  return getApiUrl("/api/manual-dispatch/final-summaries/export-excel", {
    dispatch_date: dispatchDate,
    delivery_date: deliveryDate,
  });
}


export function apiExportFinalSummariesExcel(dispatchDate, deliveryDate) {
  return fetch(getFinalSummaryExcelExportUrl(dispatchDate, deliveryDate));
}
