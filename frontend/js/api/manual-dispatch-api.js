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
    let detail = null;
    try {
      const payload = await response.json();
      detail = payload.detail;
      message = formatApiErrorDetail(payload.detail) || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw createApiError(message, response, detail);
  }

  return response.json();
}


async function requestFormData(path, formData, options = {}) {
  const response = await fetch(getApiUrl(path, options.query), {
    method: options.method || "POST",
    body: formData,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    let detail = null;
    try {
      const payload = await response.json();
      detail = payload.detail;
      message = formatApiErrorDetail(payload.detail) || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw createApiError(message, response, detail);
  }

  return response.json();
}


function createApiError(message, response, detail = null) {
  const error = new Error(message);
  error.status = response.status;
  error.detail = detail;
  return error;
}


function getFilenameFromContentDisposition(headerValue, fallbackFilename) {
  if (!headerValue) {
    return fallbackFilename;
  }
  const utf8Match = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    return decodeURIComponent(utf8Match[1].replace(/"/g, ""));
  }
  const plainMatch = headerValue.match(/filename="?([^";]+)"?/i);
  return plainMatch ? plainMatch[1] : fallbackFilename;
}


async function requestBlobDownload(path, fallbackFilename) {
  const response = await fetch(getApiUrl(path));
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    let detail = null;
    try {
      const payload = await response.json();
      detail = payload.detail;
      message = formatApiErrorDetail(payload.detail) || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw createApiError(message, response, detail);
  }

  const blob = await response.blob();
  const filename = getFilenameFromContentDisposition(
    response.headers.get("Content-Disposition"),
    fallbackFilename,
  );
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
  return { filename };
}


export async function apiGetBoard(dispatchDate) {
  return requestJson("/api/manual-dispatch/board", {
    query: { dispatch_date: dispatchDate },
  });
}


export async function apiGetDeliveryWorkspaceBoard(dispatchDate) {
  return requestJson("/api/manual-dispatch/delivery/board", {
    query: { dispatch_date: dispatchDate },
  });
}

export async function apiGetWorkspaceMigrationStatus() {
  return requestJson("/api/manual-dispatch/workspace-migration-status");
}


export async function apiGetOpShopWorkspaceBoard(dispatchDate) {
  return requestJson("/api/manual-dispatch/opshop/board", {
    query: { dispatch_date: dispatchDate },
  });
}


export async function apiGetSharedSpecifications() {
  return requestJson("/api/manual-dispatch/shared/specifications");
}


export async function apiListDeliveryRunSheets(dispatchDate, status = "") {
  return requestJson("/api/manual-dispatch/delivery/run-sheets", {
    query: { dispatch_date: dispatchDate, status },
  });
}


export async function apiListOpShopPickupCollections(dispatchDate, status = "") {
  return requestJson("/api/manual-dispatch/opshop/pickup-collections", {
    query: { dispatch_date: dispatchDate, status },
  });
}


export async function apiAssignDeliveryWorkspaceOrder(payload) {
  return requestJson("/api/manual-dispatch/delivery/assignments", {
    method: "POST",
    body: payload,
  });
}


export async function apiUnassignDeliveryWorkspaceOrder(payload) {
  return requestJson("/api/manual-dispatch/delivery/assignments/unassign", {
    method: "POST",
    body: payload,
  });
}


export async function apiAssignDeliveryWorkspaceVehicle(payload) {
  return requestJson("/api/manual-dispatch/delivery/vehicle-assignments", {
    method: "POST",
    body: payload,
  });
}


export async function apiClearDeliveryWorkspaceVehicle(payload) {
  return requestJson("/api/manual-dispatch/delivery/vehicle-assignments/clear", {
    method: "POST",
    body: payload,
  });
}


export async function apiCreateGeneratedDeliveryRunSheet(payload) {
  return requestJson("/api/manual-dispatch/delivery/run-sheets/generated", {
    method: "POST",
    body: payload,
  });
}


export async function apiSaveGeneratedDeliveryRunSheet(runSheetId, payload) {
  return requestJson(
    `/api/manual-dispatch/delivery/run-sheets/${encodeURIComponent(runSheetId)}/save`,
    {
      method: "POST",
      body: payload,
    },
  );
}


export async function apiCancelGeneratedDeliveryRunSheet(runSheetId) {
  return requestJson(
    `/api/manual-dispatch/delivery/run-sheets/${encodeURIComponent(runSheetId)}/cancel-generated`,
    { method: "POST" },
  );
}


export async function apiExportDeliveryRunSheetExcel(runSheetId) {
  return requestBlobDownload(
    `/api/manual-dispatch/delivery/run-sheets/${encodeURIComponent(runSheetId)}/export-excel`,
    "delivery-run-sheet.xlsx",
  );
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


export async function apiPreviewAttacheInvoicePdfImport(files) {
  const formData = new FormData();
  Array.from(files || []).forEach((file) => {
    formData.append("files", file);
  });
  return requestFormData("/api/manual-dispatch/orders/import-attache-pdf-preview", formData);
}


export async function apiCommitAttacheInvoicePdfImport(payload) {
  return requestJson("/api/manual-dispatch/orders/import-attache-pdf-commit", {
    method: "POST",
    body: payload,
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


export async function apiExportFinalSummaryExcel(summaryId) {
  return fetch(
    getApiUrl(
      `/api/manual-dispatch/final-summaries/${encodeURIComponent(summaryId)}/export-excel`,
    ),
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
