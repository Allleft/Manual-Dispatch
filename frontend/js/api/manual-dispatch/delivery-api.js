import { requestBlobDownload, requestFormData, requestJson } from "./shared-api.js";


export async function apiGetDeliveryWorkspaceBoard(dispatchDate) {
  return requestJson("/api/manual-dispatch/delivery/board", {
    query: { dispatch_date: dispatchDate },
  });
}

export async function apiGetDeliveryTripSummary({ deliveryDate }) {
  return requestJson("/api/manual-dispatch/delivery/trip-summary", {
    query: { delivery_date: deliveryDate },
  });
}

export async function apiGetDeliverySpecifications() {
  return requestJson("/api/manual-dispatch/delivery/specifications");
}

export async function apiClassifyDeliveryArea(suburb, postcode) {
  return requestJson("/api/manual-dispatch/delivery/area-classification", {
    method: "POST",
    body: { suburb, postcode },
  });
}

export async function apiListDeliveryRunSheets(dispatchDate, status = "") {
  return requestJson("/api/manual-dispatch/delivery/run-sheets", {
    query: { dispatch_date: dispatchDate, status },
  });
}

export async function apiListDeliveryRunSheetsByDeliveryDate(deliveryDate, status = "") {
  return requestJson("/api/manual-dispatch/delivery/run-sheets", {
    query: { delivery_date: deliveryDate, status },
  });
}

export async function apiListDeliveryRunSheetsByDispatchAndDeliveryDate(
  dispatchDate,
  deliveryDate,
  status = "",
) {
  return requestJson("/api/manual-dispatch/delivery/run-sheets", {
    query: { dispatch_date: dispatchDate, delivery_date: deliveryDate, status },
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

export async function apiCloseDeliveryRunSheet(runSheetId, payload) {
  return requestJson(
    `/api/manual-dispatch/delivery/run-sheets/${encodeURIComponent(runSheetId)}/closeout`,
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

export async function apiExportDeliveryRunSheetsExcel(deliveryDate) {
  return requestBlobDownload(
    `/api/manual-dispatch/delivery/run-sheets/export-excel?delivery_date=${encodeURIComponent(deliveryDate)}`,
    `Daily_Run_Sheets_${deliveryDate}.xlsx`,
  );
}

export async function apiCreateDeliveryOrder(payload) {
  return requestJson("/api/manual-dispatch/delivery/orders", {
    method: "POST",
    body: payload,
  });
}

export async function apiUpdateDeliveryOrder(orderId, payload) {
  return requestJson(
    `/api/manual-dispatch/delivery/orders/${encodeURIComponent(orderId)}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function apiCancelDeliveryOrder(orderId) {
  return requestJson(
    `/api/manual-dispatch/delivery/orders/${encodeURIComponent(orderId)}/cancel`,
    { method: "POST" },
  );
}

export async function apiPreviewDeliveryAttacheInvoices(files) {
  const formData = new FormData();
  Array.from(files || []).forEach((file) => {
    formData.append("files", file);
  });
  return requestFormData(
    "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview",
    formData,
  );
}

export async function apiCommitDeliveryAttacheInvoices(payload) {
  return requestJson(
    "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function apiUpdateDeliveryOrderArea(orderId, deliveryArea) {
  return requestJson(
    `/api/manual-dispatch/delivery/orders/${encodeURIComponent(orderId)}/delivery-area`,
    {
      method: "PATCH",
      body: { delivery_area: deliveryArea },
    },
  );
}

export async function apiPreviewDeliveryDockets(files) {
  const formData = new FormData();
  Array.from(files || []).forEach((file) => {
    formData.append("files", file);
  });
  return requestFormData(
    "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
    formData,
  );
}

export async function apiCommitDeliveryDockets(payload) {
  return requestJson(
    "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-commit",
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function apiCreateDeliveryDriver(payload) {
  return requestJson("/api/manual-dispatch/delivery/drivers", {
    method: "POST",
    body: payload,
  });
}

export async function apiUpdateDeliveryDriver(driverId, payload) {
  return requestJson(
    `/api/manual-dispatch/delivery/drivers/${encodeURIComponent(driverId)}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function apiDeleteDeliveryDriver(driverId) {
  return requestJson(
    `/api/manual-dispatch/delivery/drivers/${encodeURIComponent(driverId)}`,
    { method: "DELETE" },
  );
}

export async function apiCreateDeliveryVehicle(payload) {
  return requestJson("/api/manual-dispatch/delivery/vehicles", {
    method: "POST",
    body: payload,
  });
}

export async function apiUpdateDeliveryVehicle(vehicleId, payload) {
  return requestJson(
    `/api/manual-dispatch/delivery/vehicles/${encodeURIComponent(vehicleId)}`,
    {
      method: "PATCH",
      body: payload,
    },
  );
}

export async function apiDeleteDeliveryVehicle(vehicleId) {
  return requestJson(
    `/api/manual-dispatch/delivery/vehicles/${encodeURIComponent(vehicleId)}`,
    { method: "DELETE" },
  );
}
