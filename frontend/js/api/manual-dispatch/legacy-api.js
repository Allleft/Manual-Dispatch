import { getApiUrl, requestFormData, requestJson } from "./shared-api.js";


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
