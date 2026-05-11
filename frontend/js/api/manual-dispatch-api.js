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


export async function apiSaveFinalSummary(payload) {
  return requestJson("/api/manual-dispatch/final-summaries", {
    method: "POST",
    body: payload,
  });
}


export async function apiListFinalSummaries(dispatchDate) {
  return requestJson("/api/manual-dispatch/final-summaries", {
    query: { dispatch_date: dispatchDate },
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


export function getFinalSummaryExcelExportUrl(dispatchDate) {
  return getApiUrl("/api/manual-dispatch/final-summaries/export-excel", {
    dispatch_date: dispatchDate,
  });
}
