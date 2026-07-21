const API_BASE_URL =
  window.MANUAL_DISPATCH_API_BASE_URL ||
  (window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "");

let unauthorizedHandler = null;
let unauthorizedNotificationPending = false;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === "function" ? handler : null;
}

async function notifyUnauthorized(response) {
  if (response.status !== 401 || !unauthorizedHandler || unauthorizedNotificationPending) {
    return;
  }
  unauthorizedNotificationPending = true;
  try {
    await unauthorizedHandler();
  } finally {
    unauthorizedNotificationPending = false;
  }
}

export function getApiUrl(path, query = {}) {
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

export async function requestJson(path, options = {}) {
  const response = await fetch(getApiUrl(path, options.query), {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    await notifyUnauthorized(response);
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

export async function requestFormData(path, formData, options = {}) {
  const response = await fetch(getApiUrl(path, options.query), {
    method: options.method || "POST",
    body: formData,
  });

  if (!response.ok) {
    await notifyUnauthorized(response);
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

export async function requestBlobDownload(path, fallbackFilename) {
  const response = await fetch(getApiUrl(path));
  if (!response.ok) {
    await notifyUnauthorized(response);
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

export async function apiGetWorkspaceMigrationStatus() {
  return requestJson("/api/manual-dispatch/workspace-migration-status");
}

export async function apiGetSharedSpecifications() {
  return requestJson("/api/manual-dispatch/shared/specifications");
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

export async function requestResponse(path, options = {}) {
  const response = await fetch(getApiUrl(path, options.query), {
    method: options.method || "GET",
    headers: options.headers,
    body: options.body,
  });
  await notifyUnauthorized(response);
  return response;
}

export async function apiGetAccountSession() {
  return requestJson("/api/manual-dispatch/auth/session");
}

export async function apiLogoutAccount() {
  return requestJson("/api/manual-dispatch/auth/logout", {
    method: "POST",
  });
}

export async function apiResetPassword(payload) {
  return requestJson("/api/manual-dispatch/auth/reset-password", {
    method: "POST",
    body: payload,
  });
}
