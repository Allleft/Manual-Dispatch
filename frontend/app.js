import {
  apiAssignDriverVehicle,
  apiAssignTask,
  apiCancelOrder,
  apiCreateDriver,
  apiCreateOrder,
  apiCreateVehicle,
  apiDeleteDriver,
  apiDeleteVehicle,
  apiExportFinalSummariesExcel,
  apiGetBoard,
  apiGetSpecifications,
  apiListFinalSummaries,
  apiListFinalSummaryDates,
  apiLoginAccount,
  apiRegisterAccount,
  apiResetPassword,
  apiSaveFinalSummary,
  apiUnassignTask,
  apiUpdateDriver,
  apiUpdateOrder,
  apiUpdateVehicle,
  formatApiErrorDetail,
} from "./js/api/manual-dispatch-api.js";
import {
  AUTH_ACCOUNT_ID_SESSION_KEY,
  AUTH_ACCOUNT_NAME_SESSION_KEY,
  DEFAULT_DISPATCH_DATE,
  state,
} from "./js/state/app-state.js";
import {
  findDriverById,
  findVehicleById,
  getAssignedOrdersForDriver,
  getOrderByTaskId,
  getSelectedVehicleForDriver,
  getTaskKey,
  isGeneratedTask,
} from "./js/state/selectors.js";
import {
  formatOptional,
  getDisplayPalletQuantity,
  getLooseBagsQuantity,
  getUrgencyLabel,
} from "./js/utils/format-utils.js";
import {
  renderAccountStatus as renderAccountStatusView,
  renderAuthGate as renderAuthGateView,
} from "./js/render/auth-renderer.js";
import { renderFinalTripSummaries as renderFinalTripSummariesView } from "./js/render/final-summary-renderer.js";
import {
  renderAddOrderPopup as renderAddOrderPopupView,
  renderOrderDetailPopup as renderOrderDetailPopupView,
} from "./js/render/order-modal-renderer.js";
import {
  renderTaskPool as renderTaskPoolView,
  renderTaskPoolFilters as renderTaskPoolFiltersView,
} from "./js/render/task-pool-renderer.js";
import { renderDriverSummary as renderDriverSummaryView } from "./js/render/trip-summary-renderer.js";

function normalizeBoardResponse(payload) {
  return {
    dispatchDate: payload.dispatch_date || state.dispatchDate,
    orders: payload.orders || [],
    drivers: payload.drivers || [],
    vehicles: payload.vehicles || [],
    assignments: payload.assignments || [],
    driverVehicleAssignments: payload.driver_vehicle_assignments || [],
  };
}

function applyBoardResponse(payload) {
  const board = normalizeBoardResponse(payload);
  state.dispatchDate = board.dispatchDate;
  state.orders = board.orders;
  state.drivers = board.drivers;
  state.vehicles = board.vehicles;
  state.assignments = board.assignments;
  state.driverVehicleAssignments = board.driverVehicleAssignments;
  cleanupPendingSelections();
}

function getExportFilename(response, fallbackFilename) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  return match ? match[1] : fallbackFilename;
}

async function downloadExcelResponse(response, fallbackFilename) {
  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = getExportFilename(response, fallbackFilename);
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(downloadUrl);
}

function getSafeSessionStorage() {
  try {
    return window.sessionStorage;
  } catch (error) {
    return null;
  }
}

function restoreAccountSession() {
  const storage = getSafeSessionStorage();
  if (!storage) {
    return;
  }

  const accountName = storage.getItem(AUTH_ACCOUNT_NAME_SESSION_KEY) || "";
  const accountId = storage.getItem(AUTH_ACCOUNT_ID_SESSION_KEY) || "";
  if (!accountName) {
    return;
  }

  state.accountName = accountName;
  state.accountId = accountId;
  state.isLoggedIn = true;
}

function saveAccountSession(identity) {
  const storage = getSafeSessionStorage();
  if (!storage) {
    return;
  }

  storage.setItem(AUTH_ACCOUNT_NAME_SESSION_KEY, identity.account_name || "");
  storage.setItem(AUTH_ACCOUNT_ID_SESSION_KEY, String(identity.account_id || ""));
}

function clearAccountSession() {
  const storage = getSafeSessionStorage();
  if (!storage) {
    return;
  }

  storage.removeItem(AUTH_ACCOUNT_NAME_SESSION_KEY);
  storage.removeItem(AUTH_ACCOUNT_ID_SESSION_KEY);
}

function applyLoggedInAccount(identity) {
  state.accountName = identity.account_name || "";
  state.accountId = identity.account_id ? String(identity.account_id) : "";
  state.isLoggedIn = Boolean(state.accountName);
  state.loginError = "";
  state.registerError = "";
  state.resetError = "";
  state.authSuccessMessage = "";
  saveAccountSession(identity);
}

function logoutAccount() {
  state.accountName = "";
  state.accountId = "";
  state.isLoggedIn = false;
  state.authMode = "login";
  state.loginError = "";
  state.registerError = "";
  state.resetError = "";
  state.authSuccessMessage = "";
  clearAccountSession();
  renderBoard();
}

async function loadBoard(dispatchDate = state.dispatchDate, options = {}) {
  const force = Boolean(options.force);

  if (state.isSpecificationModalOpen && !force) {
    state.specificationDirty = true;
    return;
  }

  state.dispatchDate = dispatchDate || DEFAULT_DISPATCH_DATE;
  state.isLoading = true;
  state.errorMessage = "";
  renderBoard();

  try {
    const payload = await apiGetBoard(state.dispatchDate);

    if (state.isSpecificationModalOpen && !force) {
      state.specificationDirty = true;
      return;
    }

    applyBoardResponse(payload);
  } catch (error) {
    showError(`Unable to load board data. ${error.message}`);
  } finally {
    if (!(state.isSpecificationModalOpen && !force)) {
      state.isLoading = false;
      state.isSaving = false;
      renderBoard();
    }
  }
}

function syncHistoryDateSelection() {
  if (state.finalSummaryDates.includes(state.historyDate)) {
    return;
  }
  if (state.finalSummaryDates.includes(state.dispatchDate)) {
    state.historyDate = state.dispatchDate;
    return;
  }
  state.historyDate = state.finalSummaryDates[0] || state.dispatchDate || DEFAULT_DISPATCH_DATE;
}

async function loadFinalSummaryDates(options = {}) {
  try {
    state.finalSummaryDates = await apiListFinalSummaryDates();
    syncHistoryDateSelection();
  } catch (error) {
    state.historyError = `Unable to load Final Trip Summary dates. ${error.message}`;
  } finally {
    if (options.render !== false) {
      renderFinalTripSummaries();
    }
  }
}

function showError(message) {
  state.errorMessage = message;
}

function clearError() {
  state.errorMessage = "";
}

function getDefaultAddOrderForm() {
  return {
    invoice_number: "",
    company_name: "",
    phone: "",
    delivery_address: "",
    suburb: "",
    postcode: "",
    delivery_date: state.dispatchDate || DEFAULT_DISPATCH_DATE,
    zone: "",
    urgency: "Normal",
    preferred_driver_id: "",
    pallet_quantity: "0",
    loose_bags_quantity: "0",
    start_time: "",
    end_time: "",
    note: "",
  };
}

function getDefaultDriverSpecificationForm(driver = {}) {
  return {
    name: driver.name || "",
    license_no: driver.license_no || "",
    email: driver.email || "",
    phone_number: driver.phone_number || "",
    start_time: driver.start_time || "",
    end_time: driver.end_time || "",
    is_available: driver.is_available !== false,
    pallet_only: Boolean(driver.pallet_only),
    preferred_zone: driver.preferred_zone || "",
  };
}

function getDefaultVehicleSpecificationForm(vehicle = {}) {
  return {
    rego: vehicle.rego || "",
    type: vehicle.type || "",
    is_available: vehicle.is_available !== false,
    pallet_capacity: String(vehicle.pallet_capacity ?? 0),
    tub_capacity: String(vehicle.tub_capacity ?? 0),
    trolley_capacity: String(vehicle.trolley_capacity ?? 0),
    stillage_capacity: String(vehicle.stillage_capacity ?? 0),
  };
}

function getDriverSpecificationPayload(form) {
  return {
    ...form,
    is_available: Boolean(form.is_available),
    pallet_only: Boolean(form.pallet_only),
  };
}

function getVehicleSpecificationPayload(form) {
  return {
    ...form,
    is_available: Boolean(form.is_available),
    pallet_capacity: Number(form.pallet_capacity || 0),
    tub_capacity: Number(form.tub_capacity || 0),
    trolley_capacity: Number(form.trolley_capacity || 0),
    stillage_capacity: Number(form.stillage_capacity || 0),
  };
}

function openAddOrder() {
  state.isAddOrderOpen = true;
  state.addOrderError = "";
  state.addOrderForm = getDefaultAddOrderForm();
  renderAddOrderPopup();
}

function closeAddOrder() {
  state.isAddOrderOpen = false;
  state.addOrderError = "";
  state.addOrderForm = {};
  renderAddOrderPopup();
}

async function openSpecificationModal() {
  state.isSpecificationModalOpen = true;
  state.specificationError = "";
  state.specificationDirty = false;
  state.specificationLoading = false;
  state.driverSpecificationForm = null;
  state.driverSpecificationEditingId = "";
  state.vehicleSpecificationForm = null;
  state.vehicleSpecificationEditingId = "";
  renderSpecificationShell();
  renderSpecificationPanel();
  await loadSpecificationsIntoState();
  renderSpecificationPanel();
}

async function closeSpecificationModal() {
  const shouldReloadBoard = state.specificationDirty;
  const root = document.querySelector("#specification-root");
  state.isSpecificationModalOpen = false;
  state.specificationError = "";
  state.specificationDirty = false;
  state.specificationLoading = false;
  state.specificationSaving = false;
  state.driverSpecificationForm = null;
  state.driverSpecificationEditingId = "";
  state.vehicleSpecificationForm = null;
  state.vehicleSpecificationEditingId = "";
  if (root) {
    root.innerHTML = "";
  }

  if (shouldReloadBoard) {
    await loadBoard(state.dispatchDate, { force: true });
  }
}

async function loadSpecificationsIntoState() {
  state.specificationLoading = true;
  clearSpecificationError();

  try {
    const payload = await apiGetSpecifications();
    state.specificationDrivers = payload.drivers || [];
    state.specificationVehicles = payload.vehicles || [];
  } catch (error) {
    showSpecificationError(`Unable to load specifications. ${error.message}`);
  } finally {
    state.specificationLoading = false;
  }
}

function showSpecificationError(message) {
  state.specificationError = message;
  const errorElement = document.querySelector("#specification-error");
  if (errorElement) {
    errorElement.hidden = !message;
    errorElement.textContent = message || "";
  }
}

function clearSpecificationError() {
  showSpecificationError("");
}

function startAddDriverSpecification() {
  state.specificationActiveTab = "drivers";
  state.driverSpecificationEditingId = "";
  state.driverSpecificationForm = getDefaultDriverSpecificationForm();
  updateSpecificationTabButtons();
  renderSpecificationPanel({ preserveScroll: true });
}

function startEditDriverSpecification(driver) {
  state.specificationActiveTab = "drivers";
  state.driverSpecificationEditingId = driver.driver_id;
  state.driverSpecificationForm = getDefaultDriverSpecificationForm(driver);
  updateSpecificationTabButtons();
  renderSpecificationPanel({ preserveScroll: true });
}

function cancelDriverSpecificationForm() {
  state.driverSpecificationEditingId = "";
  state.driverSpecificationForm = null;
  renderSpecificationPanel({ preserveScroll: true });
}

function updateDriverSpecificationForm(field, value) {
  state.driverSpecificationForm = {
    ...state.driverSpecificationForm,
    [field]: value,
  };
}

function startAddVehicleSpecification() {
  state.specificationActiveTab = "vehicles";
  state.vehicleSpecificationEditingId = "";
  state.vehicleSpecificationForm = getDefaultVehicleSpecificationForm();
  updateSpecificationTabButtons();
  renderSpecificationPanel({ preserveScroll: true });
}

function startEditVehicleSpecification(vehicle) {
  state.specificationActiveTab = "vehicles";
  state.vehicleSpecificationEditingId = vehicle.vehicle_id;
  state.vehicleSpecificationForm = getDefaultVehicleSpecificationForm(vehicle);
  updateSpecificationTabButtons();
  renderSpecificationPanel({ preserveScroll: true });
}

function cancelVehicleSpecificationForm() {
  state.vehicleSpecificationEditingId = "";
  state.vehicleSpecificationForm = null;
  renderSpecificationPanel({ preserveScroll: true });
}

function updateVehicleSpecificationForm(field, value) {
  state.vehicleSpecificationForm = {
    ...state.vehicleSpecificationForm,
    [field]: value,
  };
}

function updateSpecificationDriverLocal(driverId, updates) {
  state.specificationDrivers = state.specificationDrivers.map((driver) =>
    driver.driver_id === driverId ? { ...driver, ...updates } : driver,
  );
}

function updateSpecificationVehicleLocal(vehicleId, updates) {
  state.specificationVehicles = state.specificationVehicles.map((vehicle) =>
    vehicle.vehicle_id === vehicleId ? { ...vehicle, ...updates } : vehicle,
  );
}

function updateAddOrderForm(field, value) {
  state.addOrderForm = {
    ...state.addOrderForm,
    [field]: value,
  };
}

function getAddOrderPayload() {
  return {
    ...state.addOrderForm,
    pallet_quantity: Number(state.addOrderForm.pallet_quantity || 0),
    loose_bags_quantity: Number(state.addOrderForm.loose_bags_quantity || 0),
  };
}

function getOrderEditForm(order) {
  return {
    invoice_number: order.invoice_number || "",
    company_name: order.company_name || "",
    phone: order.phone || "",
    delivery_address: order.delivery_address || "",
    suburb: order.suburb || "",
    postcode: order.postcode || "",
    zone: order.zone || "",
    urgency: getUrgencyLabel(order),
    preferred_driver_id: order.preferred_driver_id || "",
    pallet_quantity: String(getDisplayPalletQuantity(order)),
    loose_bags_quantity: String(getLooseBagsQuantity(order)),
    start_time: order.start_time || "",
    end_time: order.end_time || "",
    note: order.note || "",
  };
}

function startOrderEdit(order) {
  state.isOrderEditMode = true;
  state.orderEditError = "";
  state.orderEditForm = getOrderEditForm(order);
  renderOrderDetailPopup();
}

function cancelOrderEdit() {
  state.isOrderEditMode = false;
  state.orderEditError = "";
  state.orderEditForm = {};
  renderOrderDetailPopup();
}

function updateOrderEditForm(field, value) {
  state.orderEditForm = {
    ...state.orderEditForm,
    [field]: value,
  };
}

function getOrderEditPayload() {
  return {
    ...state.orderEditForm,
    pallet_quantity: Number(state.orderEditForm.pallet_quantity || 0),
    loose_bags_quantity: Number(state.orderEditForm.loose_bags_quantity || 0),
  };
}

async function exportFinalSummariesExcel(dispatchDate) {
  const response = await apiExportFinalSummariesExcel(dispatchDate);
  if (!response.ok) {
    let message = `Export failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = formatApiErrorDetail(payload.detail) || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  await downloadExcelResponse(response, `final-trip-summary-${dispatchDate}.xlsx`);
}

async function handleCreateOrder() {
  if (state.isSaving) {
    return;
  }

  state.isSaving = true;
  state.addOrderError = "";
  renderAddOrderPopup();

  try {
    await apiCreateOrder(getAddOrderPayload());
    closeAddOrder();
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    state.addOrderError = `Unable to save Order. ${error.message}`;
    renderAddOrderPopup();
  }
}

async function handleUpdateOrder(orderId) {
  if (state.isSaving) {
    return;
  }

  state.isSaving = true;
  state.orderEditError = "";
  renderOrderDetailPopup();

  try {
    await apiUpdateOrder(orderId, getOrderEditPayload());
    state.isOrderEditMode = false;
    state.orderEditError = "";
    state.orderEditForm = {};
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    state.orderEditError = `Unable to save changes. ${error.message}`;
    renderOrderDetailPopup();
  }
}

async function handleCancelOrder(orderId) {
  if (state.isSaving) {
    return;
  }

  const confirmed = window.confirm(
    "Cancel this Order? Cancelled Orders are hidden from the Task Pool and excluded from export.",
  );
  if (!confirmed) {
    return;
  }

  state.isSaving = true;
  clearError();
  renderOrderDetailPopup();

  try {
    await apiCancelOrder(orderId);
    closeOrderDetail();
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    showError(`Unable to cancel Order. ${error.message}`);
    renderBoard();
  }
}

async function refreshSpecificationsOnly({ markDirty = true } = {}) {
  if (markDirty) {
    state.specificationDirty = true;
  }
  await loadSpecificationsIntoState();
  renderSpecificationPanel({ preserveScroll: true });
}

async function handleSaveDriverSpecification() {
  if (state.specificationSaving || !state.driverSpecificationForm) {
    return;
  }

  state.specificationSaving = true;
  state.specificationError = "";
  renderSpecificationPanel({ preserveScroll: true });

  try {
    const payload = getDriverSpecificationPayload(state.driverSpecificationForm);
    if (state.driverSpecificationEditingId) {
      await apiUpdateDriver(state.driverSpecificationEditingId, payload);
    } else {
      await apiCreateDriver(payload);
    }
    state.driverSpecificationEditingId = "";
    state.driverSpecificationForm = null;
    await refreshSpecificationsOnly();
  } catch (error) {
    state.specificationError = `Unable to save Driver. ${error.message}`;
    showSpecificationError(state.specificationError);
  } finally {
    state.specificationSaving = false;
    renderSpecificationPanel({ preserveScroll: true });
  }
}

async function handleToggleDriverAvailability(driver, isAvailable, checkbox) {
  const previousValue = driver.is_available !== false;
  clearSpecificationError();
  if (checkbox) {
    checkbox.disabled = true;
  }

  try {
    await apiUpdateDriver(driver.driver_id, {
      ...getDefaultDriverSpecificationForm(driver),
      is_available: isAvailable,
    });

    updateSpecificationDriverLocal(driver.driver_id, { is_available: isAvailable });
    driver.is_available = isAvailable;
    state.specificationDirty = true;
  } catch (error) {
    updateSpecificationDriverLocal(driver.driver_id, { is_available: previousValue });
    driver.is_available = previousValue;

    if (checkbox) {
      checkbox.checked = previousValue;
    }

    showSpecificationError(`Unable to update Driver availability. ${error.message}`);
  } finally {
    if (checkbox) {
      checkbox.disabled = false;
    }
  }
}

async function handleDeleteDriverSpecification(driverId) {
  const confirmed = window.confirm("Are you sure you want to delete this driver?");
  if (!confirmed) {
    return;
  }

  state.specificationSaving = true;
  state.specificationError = "";
  renderSpecificationPanel({ preserveScroll: true });

  try {
    await apiDeleteDriver(driverId);
    await refreshSpecificationsOnly();
  } catch (error) {
    state.specificationError = `Unable to delete Driver. ${error.message}`;
    showSpecificationError(state.specificationError);
  } finally {
    state.specificationSaving = false;
    renderSpecificationPanel({ preserveScroll: true });
  }
}

async function handleSaveVehicleSpecification() {
  if (state.specificationSaving || !state.vehicleSpecificationForm) {
    return;
  }

  state.specificationSaving = true;
  state.specificationError = "";
  renderSpecificationPanel({ preserveScroll: true });

  try {
    const payload = getVehicleSpecificationPayload(state.vehicleSpecificationForm);
    if (state.vehicleSpecificationEditingId) {
      await apiUpdateVehicle(state.vehicleSpecificationEditingId, payload);
    } else {
      await apiCreateVehicle(payload);
    }
    state.vehicleSpecificationEditingId = "";
    state.vehicleSpecificationForm = null;
    await refreshSpecificationsOnly();
  } catch (error) {
    state.specificationError = `Unable to save Vehicle. ${error.message}`;
    showSpecificationError(state.specificationError);
  } finally {
    state.specificationSaving = false;
    renderSpecificationPanel({ preserveScroll: true });
  }
}

async function handleToggleVehicleAvailability(vehicle, isAvailable, checkbox) {
  const previousValue = vehicle.is_available !== false;
  clearSpecificationError();
  if (checkbox) {
    checkbox.disabled = true;
  }

  try {
    await apiUpdateVehicle(vehicle.vehicle_id, {
      ...getDefaultVehicleSpecificationForm(vehicle),
      is_available: isAvailable,
    });

    updateSpecificationVehicleLocal(vehicle.vehicle_id, { is_available: isAvailable });
    vehicle.is_available = isAvailable;
    state.specificationDirty = true;
  } catch (error) {
    updateSpecificationVehicleLocal(vehicle.vehicle_id, { is_available: previousValue });
    vehicle.is_available = previousValue;

    if (checkbox) {
      checkbox.checked = previousValue;
    }

    showSpecificationError(`Unable to update Vehicle availability. ${error.message}`);
  } finally {
    if (checkbox) {
      checkbox.disabled = false;
    }
  }
}

async function handleDeleteVehicleSpecification(vehicleId) {
  const confirmed = window.confirm("Are you sure you want to delete this vehicle?");
  if (!confirmed) {
    return;
  }

  state.specificationSaving = true;
  state.specificationError = "";
  renderSpecificationPanel({ preserveScroll: true });

  try {
    await apiDeleteVehicle(vehicleId);
    await refreshSpecificationsOnly();
  } catch (error) {
    state.specificationError = `Unable to delete Vehicle. ${error.message}`;
    showSpecificationError(state.specificationError);
  } finally {
    state.specificationSaving = false;
    renderSpecificationPanel({ preserveScroll: true });
  }
}

function normalizeFinalSummary(summary) {
  return {
    summary_id: summary.summary_id || "",
    dispatch_date: summary.dispatch_date || state.dispatchDate,
    driver_id: summary.driver_id || "",
    driver_name: summary.driver_name || summary.driver_name_snapshot || "",
    driver_name_snapshot: summary.driver_name_snapshot || summary.driver_name || "",
    vehicle_id: summary.vehicle_id || "",
    vehicle_rego: summary.vehicle_rego || summary.vehicle_rego_snapshot || "No vehicle selected",
    vehicle_rego_snapshot: summary.vehicle_rego_snapshot || summary.vehicle_rego || "No vehicle selected",
    total_pallets: Number(summary.total_pallets || 0),
    total_loose_bags: Number(summary.total_loose_bags || 0),
    status: summary.status || (summary.summary_id ? "SAVED" : "LOCKED"),
    generated_at: summary.generated_at || "",
    saved_at: summary.saved_at || "",
    saved_by_account_name:
      summary.saved_by_account_name ||
      (summary.summary_id ? "Unknown" : state.accountName || "Unknown"),
    saved_by_account_id: summary.saved_by_account_id || "",
    trips: (summary.trips || [])
      .map((trip) => ({
        trip_no: trip.trip_no,
        orders: (trip.orders || []).map((order) => ({
          row_id: order.row_id || "",
          row_no: Number(order.row_no || 0),
          task_type: order.task_type || "ORDER",
          task_id: order.task_id || order.order_id || order.order_id_snapshot || "",
          order_id: order.order_id || order.order_id_snapshot || order.task_id || "",
          invoice_number: order.invoice_number || order.invoice_number_snapshot || "",
          company_name: order.company_name || order.company_name_snapshot || "",
          suburb: order.suburb || order.suburb_snapshot || "",
          delivery_address: order.delivery_address || order.delivery_address_snapshot || "",
          product: order.product || order.product_snapshot || "",
          pallet_quantity: Number(
            order.pallet_quantity ?? order.pallet_quantity_snapshot ?? 0,
          ),
          loose_bags_quantity: Number(
            order.loose_bags_quantity ?? order.loose_bags_quantity_snapshot ?? 0,
          ),
          note: order.note || order.note_snapshot || "",
        })),
      }))
      .filter((trip) => trip.orders.length > 0),
  };
}

function getPendingSelection(orderId) {
  if (!state.pendingSelections[orderId]) {
    state.pendingSelections[orderId] = { driver_id: "", trip_no: "trip1" };
  }
  return state.pendingSelections[orderId];
}

function updatePendingSelection(orderId, updates) {
  state.pendingSelections[orderId] = {
    ...getPendingSelection(orderId),
    ...updates,
  };
}

function cleanupPendingSelections() {
  const orderIds = new Set(state.orders.map((order) => order.order_id));
  const assignedOrderIds = new Set(
    state.assignments
      .filter((assignment) => assignment.task_type === "ORDER")
      .map((assignment) => assignment.task_id),
  );
  const driverIds = new Set(state.drivers.map((driver) => driver.driver_id));

  Object.entries(state.pendingSelections).forEach(([orderId, selection]) => {
    if (!orderIds.has(orderId) || assignedOrderIds.has(orderId)) {
      delete state.pendingSelections[orderId];
      return;
    }

    if (selection.driver_id && !driverIds.has(selection.driver_id)) {
      selection.driver_id = "";
    }

    if (!["trip1", "trip2"].includes(selection.trip_no)) {
      selection.trip_no = "trip1";
    }
  });
}

function openOrderDetail(orderId) {
  state.activeOrderDetailId = orderId;
  state.isOrderEditMode = false;
  state.orderEditError = "";
  state.orderEditForm = {};
  renderOrderDetailPopup();
}

function closeOrderDetail() {
  state.activeOrderDetailId = "";
  state.isOrderEditMode = false;
  state.orderEditError = "";
  state.orderEditForm = {};
  renderOrderDetailPopup();
}

async function handleAssign(orderId) {
  const selection = getPendingSelection(orderId);
  if (!selection.driver_id || state.isSaving) {
    return;
  }

  state.isSaving = true;
  clearError();
  renderBoard();

  try {
    await apiAssignTask({
      dispatch_date: state.dispatchDate,
      task_type: "ORDER",
      task_id: orderId,
      driver_id: selection.driver_id,
      trip_no: selection.trip_no || "trip1",
    });
    delete state.pendingSelections[orderId];
    closeOrderDetail();
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    showError(`Unable to assign task. ${error.message}`);
    renderBoard();
  }
}

async function handleUnassign(taskType, taskId) {
  if (state.isSaving) {
    return;
  }

  state.isSaving = true;
  clearError();
  renderBoard();

  try {
    await apiUnassignTask({
      dispatch_date: state.dispatchDate,
      task_type: taskType,
      task_id: taskId,
    });
    updatePendingSelection(taskId, { driver_id: "", trip_no: "trip1" });
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    showError(`Unable to unassign task. ${error.message}`);
    renderBoard();
  }
}

async function handleVehicleChange(driverId, vehicleId) {
  if (state.isSaving) {
    return;
  }

  state.isSaving = true;
  clearError();
  renderBoard();

  try {
    await apiAssignDriverVehicle({
      dispatch_date: state.dispatchDate,
      driver_id: driverId,
      vehicle_id: vehicleId || null,
    });
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    showError(`Unable to update vehicle selection. ${error.message}`);
    renderBoard();
  }
}

function buildFinalTripSummarySnapshot(driverId) {
  const driver = findDriverById(driverId);
  if (!driver) {
    throw new Error(`Driver does not exist: ${driverId}`);
  }

  const selectedVehicle = getSelectedVehicleForDriver(driverId);
  const assignments = getAssignmentsForDriver(driverId);
  const trips = ["trip1", "trip2"]
    .map((tripNo) => {
      const tripOrders = assignments
        .filter((assignment) => assignment.trip_no === tripNo)
        .map((assignment) => {
          const order = getOrderByTaskId(assignment.task_id);
          if (!order) {
            return null;
          }
          return {
            task_type: assignment.task_type,
            task_id: assignment.task_id,
            order_id: order.order_id,
            order_id_snapshot: order.order_id,
            invoice_number_snapshot: order.invoice_number || "",
            company_name_snapshot: order.company_name || "",
            suburb_snapshot: order.suburb || "",
            delivery_address_snapshot: order.delivery_address || "",
            product_snapshot: "",
            pallet_quantity_snapshot: getDisplayPalletQuantity(order),
            loose_bags_quantity_snapshot: getLooseBagsQuantity(order),
            note_snapshot: order.note || "",
            company_name: order.company_name || "",
            suburb: order.suburb || "",
            invoice_number: order.invoice_number || "",
            delivery_address: order.delivery_address || "",
            pallet_quantity: getDisplayPalletQuantity(order),
            loose_bags_quantity: getLooseBagsQuantity(order),
            note: order.note || "",
            product: "",
          };
        })
        .filter(Boolean);

      return {
        trip_no: tripNo,
        orders: tripOrders,
      };
    })
    .filter((trip) => trip.orders.length > 0);

  const allOrders = trips.flatMap((trip) => trip.orders);

  return {
    generated_at: new Date().toISOString(),
    dispatch_date: state.dispatchDate,
    driver_id: driver.driver_id,
    driver_name: driver.name,
    driver_name_snapshot: driver.name,
    vehicle_id: selectedVehicle ? selectedVehicle.vehicle_id : "",
    vehicle_rego: selectedVehicle ? selectedVehicle.rego : "No vehicle selected",
    vehicle_rego_snapshot: selectedVehicle ? selectedVehicle.rego : "No vehicle selected",
    total_pallets: allOrders.reduce((total, order) => total + Number(order.pallet_quantity || 0), 0),
    total_loose_bags: allOrders.reduce((total, order) => total + Number(order.loose_bags_quantity || 0), 0),
    saved_by_account_name: state.accountName || "",
    saved_by_account_id: state.accountId || "",
    status: "LOCKED",
    trips,
  };
}

async function handleGenerateDriverSummary(driverId) {
  if (state.isSaving || state.isLoading) {
    return;
  }

  if (state.finalTripSummaries[driverId]) {
    showError("Final Trip Summary for this driver is already generated and locked.");
    renderBoard();
    return;
  }

  const assignedOrders = getAssignedOrdersForDriver(driverId);
  if (assignedOrders.length === 0) {
    showError("Assign at least one Order before generating a Final Trip Summary.");
    renderBoard();
    return;
  }

  let snapshot;
  try {
    snapshot = buildFinalTripSummarySnapshot(driverId);
  } catch (error) {
    showError(`Unable to generate Final Trip Summary. ${error.message}`);
    renderBoard();
    return;
  }

  if (snapshot.trips.length === 0) {
    showError("No Order tasks are available to include in the Final Trip Summary.");
    renderBoard();
    return;
  }

  state.finalTripSummaries[driverId] = snapshot;
  state.finalSummaryGlobalSaveError = "";
  state.finalSummaryGlobalSaveSuccess = "";
  snapshot.trips.forEach((trip) => {
    trip.orders.forEach((order) => {
      state.generatedTaskKeys.add(getTaskKey(order.task_type, order.task_id));
    });
  });

  state.isSaving = true;
  clearError();
  renderBoard();

  const generatedTasks = snapshot.trips.flatMap((trip) => trip.orders);

  try {
    await Promise.all(
      generatedTasks.map((order) =>
        apiUnassignTask({
          dispatch_date: state.dispatchDate,
          task_type: order.task_type,
          task_id: order.task_id,
        }),
      ),
    );
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    showError(`Final Trip Summary was captured, but clearing editable assignments failed. ${error.message}`);
    renderBoard();
  }
}

function getFinalSummarySavePayload(summary) {
  const normalized = normalizeFinalSummary(summary);
  return {
    dispatch_date: normalized.dispatch_date,
    driver_id: normalized.driver_id,
    driver_name_snapshot: normalized.driver_name_snapshot || normalized.driver_name,
    vehicle_id: normalized.vehicle_id || null,
    vehicle_rego_snapshot: normalized.vehicle_rego_snapshot || "No vehicle selected",
    total_pallets: normalized.total_pallets,
    total_loose_bags: normalized.total_loose_bags,
    generated_at: normalized.generated_at,
    saved_by_account_name: state.accountName || normalized.saved_by_account_name,
    saved_by_account_id: state.accountId || normalized.saved_by_account_id || null,
    trips: normalized.trips.map((trip) => ({
      trip_no: trip.trip_no,
      orders: trip.orders.map((order) => ({
        task_type: order.task_type,
        task_id: order.task_id,
        order_id_snapshot: order.order_id,
        invoice_number_snapshot: order.invoice_number,
        company_name_snapshot: order.company_name,
        suburb_snapshot: order.suburb,
        delivery_address_snapshot: order.delivery_address,
        product_snapshot: order.product,
        pallet_quantity_snapshot: order.pallet_quantity,
        loose_bags_quantity_snapshot: order.loose_bags_quantity,
        note_snapshot: order.note,
      })),
    })),
  };
}

function getUnsavedFinalSummaries() {
  return Object.values(state.finalTripSummaries)
    .map(normalizeFinalSummary)
    .filter((summary) => !summary.summary_id);
}

async function ensureNoDuplicateFinalSummaries(summaries) {
  const summariesByDate = new Map();
  summaries.forEach((summary) => {
    const existing = summariesByDate.get(summary.dispatch_date) || [];
    existing.push(summary);
    summariesByDate.set(summary.dispatch_date, existing);
  });

  for (const [dispatchDate, dateSummaries] of summariesByDate.entries()) {
    const savedSummaries = await apiListFinalSummaries(dispatchDate);
    const savedDriverIds = new Set((savedSummaries || []).map((summary) => summary.driver_id));
    const duplicate = dateSummaries.find((summary) => savedDriverIds.has(summary.driver_id));
    if (duplicate) {
      throw new Error("Final Summary for this driver and dispatch date has already been saved.");
    }
  }
}

async function handleSaveAllFinalSummaries() {
  if (state.isSaving || state.isSavingFinalSummaries || state.isLoading) {
    return;
  }

  const unsavedSummaries = getUnsavedFinalSummaries();
  state.finalSummaryGlobalSaveError = "";
  state.finalSummaryGlobalSaveSuccess = "";

  if (!state.isLoggedIn || !state.accountName) {
    state.finalSummaryGlobalSaveError =
      "Please log in before saving and exporting Final Trip Summary.";
    renderFinalTripSummaries();
    return;
  }

  if (unsavedSummaries.length === 0) {
    state.finalSummaryGlobalSaveError = "Generate at least one Final Trip Summary before saving and exporting.";
    renderFinalTripSummaries();
    return;
  }

  state.isSavingFinalSummaries = true;
  state.isSaving = true;
  clearError();
  renderBoard();

  try {
    await ensureNoDuplicateFinalSummaries(unsavedSummaries);

    const savedSummaries = [];
    for (const summary of unsavedSummaries) {
      const savedSummary = normalizeFinalSummary(
        await apiSaveFinalSummary(getFinalSummarySavePayload(summary)),
      );
      state.finalTripSummaries[savedSummary.driver_id] = savedSummary;
      savedSummaries.push(savedSummary);
    }

    await exportFinalSummariesExcel(state.dispatchDate);

    state.finalSummaryGlobalSaveSuccess = `Final Trip Summary saved and exported by ${state.accountName}.`;
    state.historyLoaded = false;
    await loadFinalSummaryDates({ render: false });
    state.isSavingFinalSummaries = false;
    await loadBoard(state.dispatchDate);
  } catch (error) {
    state.isSaving = false;
    state.isSavingFinalSummaries = false;
    state.finalSummaryGlobalSaveError = `Unable to save and export Final Summary. ${error.message}`;
    renderBoard();
  }
}

async function handleLoadFinalSummaryHistory() {
  if (state.isSaving || state.isLoading || state.isHistoryLoading) {
    return;
  }

  state.isHistoryLoading = true;
  state.historyError = "";
  clearError();
  renderBoard();

  try {
    const summaries = await apiListFinalSummaries(state.historyDate || state.dispatchDate);
    state.finalSummaryHistory = (summaries || []).map(normalizeFinalSummary);
    state.historyLoaded = true;
  } catch (error) {
    state.historyError = `Unable to load Final Trip Summary history. ${error.message}`;
  } finally {
    state.isHistoryLoading = false;
    renderBoard();
  }
}

async function handleLogin(event) {
  event.preventDefault();
  if (state.isAuthLoading) {
    return;
  }

  const form = event.currentTarget;
  const accountNameInput = form.querySelector('input[name="account_name"]');
  const passwordInput = form.querySelector('input[name="password"]');
  const accountName = accountNameInput ? accountNameInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value : "";

  state.isAuthLoading = true;
  state.loginError = "";
  state.authSuccessMessage = "";
  renderAuthGate();

  try {
    const identity = await apiLoginAccount({ account_name: accountName, password });
    applyLoggedInAccount(identity);
  } catch (error) {
    state.loginError = error.message || "Invalid account name or password";
  } finally {
    if (passwordInput) {
      passwordInput.value = "";
    }
    state.isAuthLoading = false;
    renderBoard();
  }
}

async function handleRegister(event) {
  event.preventDefault();
  if (state.isAuthLoading) {
    return;
  }

  const form = event.currentTarget;
  const accountNameInput = form.querySelector('input[name="account_name"]');
  const passwordInput = form.querySelector('input[name="password"]');
  const confirmPasswordInput = form.querySelector('input[name="confirm_password"]');
  const accountName = accountNameInput ? accountNameInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value : "";
  const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : "";

  state.isAuthLoading = true;
  state.registerError = "";
  state.authSuccessMessage = "";
  renderAuthGate();

  try {
    const identity = await apiRegisterAccount({
      account_name: accountName,
      password,
      confirm_password: confirmPassword,
    });
    applyLoggedInAccount(identity);
  } catch (error) {
    state.registerError = error.message || "Unable to create account";
  } finally {
    if (passwordInput) {
      passwordInput.value = "";
    }
    if (confirmPasswordInput) {
      confirmPasswordInput.value = "";
    }
    state.isAuthLoading = false;
    renderBoard();
  }
}

async function handleResetPassword(event) {
  event.preventDefault();
  if (state.isAuthLoading) {
    return;
  }

  const form = event.currentTarget;
  const accountNameInput = form.querySelector('input[name="account_name"]');
  const resetCodeInput = form.querySelector('input[name="admin_reset_code"]');
  const passwordInput = form.querySelector('input[name="new_password"]');
  const confirmPasswordInput = form.querySelector('input[name="confirm_password"]');
  const accountName = accountNameInput ? accountNameInput.value.trim() : "";
  const adminResetCode = resetCodeInput ? resetCodeInput.value : "";
  const newPassword = passwordInput ? passwordInput.value : "";
  const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : "";

  state.isAuthLoading = true;
  state.resetError = "";
  state.authSuccessMessage = "";
  renderAuthGate();

  try {
    await apiResetPassword({
      account_name: accountName,
      admin_reset_code: adminResetCode,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    state.authMode = "login";
    state.authSuccessMessage = "Password reset successfully. Please log in with your new password.";
  } catch (error) {
    state.resetError = "Unable to reset password. Please check your details or contact an administrator.";
  } finally {
    if (resetCodeInput) {
      resetCodeInput.value = "";
    }
    if (passwordInput) {
      passwordInput.value = "";
    }
    if (confirmPasswordInput) {
      confirmPasswordInput.value = "";
    }
    state.isAuthLoading = false;
    renderBoard();
  }
}

function switchAuthMode(mode) {
  state.authMode = mode;
  state.loginError = "";
  state.registerError = "";
  state.resetError = "";
  state.authSuccessMessage = "";
  renderAuthGate();
}

function renderAccountStatus() {
  renderAccountStatusView({ onLogout: logoutAccount });
}

function renderAuthGate() {
  renderAuthGateView({
    onLogin: handleLogin,
    onRegister: handleRegister,
    onResetPassword: handleResetPassword,
    onSwitchAuthMode: switchAuthMode,
  });
}

function renderBoardControls() {
  const dateInput = document.querySelector("#dispatch-date");
  const specificationButton = document.querySelector("#specification-button");
  const addOrderButton = document.querySelector("#add-order-button");
  const status = document.querySelector("#board-status");
  const error = document.querySelector("#board-error");

  if (!dateInput) {
    return;
  }

  dateInput.value = state.dispatchDate;
  dateInput.disabled = state.isLoading || state.isSaving;

  if (specificationButton) {
    specificationButton.disabled = state.isLoading || state.isSaving;
  }

  if (addOrderButton) {
    addOrderButton.disabled = state.isLoading || state.isSaving;
  }

  if (status) {
    status.textContent = state.isLoading
      ? "Loading board data..."
      : state.isSaving
        ? "Saving manual dispatch change..."
        : `Dispatch Date: ${state.dispatchDate}`;
  }

  if (error) {
    error.hidden = !state.errorMessage;
    error.textContent = state.errorMessage;
  }

  dateInput.onchange = () => {
    const nextDate = dateInput.value || DEFAULT_DISPATCH_DATE;
    state.dispatchDate = nextDate;
    state.finalTripSummaries = {};
    state.generatedTaskKeys = new Set();
    state.isSavingFinalSummaries = false;
    state.finalSummaryGlobalSaveError = "";
    state.finalSummaryGlobalSaveSuccess = "";
    state.finalSummaryHistory = [];
    state.historyLoaded = false;
    state.historyError = "";
    state.historyDate = nextDate;
    loadBoard(nextDate);
    loadFinalSummaryDates();
  };

  if (specificationButton) {
    specificationButton.onclick = () => {
      openSpecificationModal();
    };
  }

  if (addOrderButton) {
    addOrderButton.onclick = () => {
      openAddOrder();
    };
  }
}

function renderTaskPoolFilters() {
  renderTaskPoolFiltersView({
    onSearchChange: (value) => {
      state.taskPoolSearch = value;
      renderTaskPoolFilters();
      renderTaskPool();
    },
    onUrgencyChange: (value) => {
      state.urgencyFilter = value;
      renderTaskPoolFilters();
      renderTaskPool();
    },
  });
}

function renderTaskPool() {
  renderTaskPoolView({
    getPendingSelection,
    onOpenOrderDetail: openOrderDetail,
    onPendingSelectionChange: updatePendingSelection,
    onAssign: handleAssign,
  });
}
function renderDriverSummary() {
  renderDriverSummaryView({
    onVehicleChange: handleVehicleChange,
    onGenerateDriverSummary: handleGenerateDriverSummary,
    onOpenOrderDetail: openOrderDetail,
    onUnassign: handleUnassign,
  });
}
function renderFinalTripSummaries() {
  renderFinalTripSummariesView({
    getUnsavedFinalSummaries,
    normalizeFinalSummary,
    onHistoryDateChange: (historyDate) => {
      state.historyDate = historyDate;
      state.historyLoaded = false;
      state.historyError = "";
      state.finalSummaryHistory = [];
      renderFinalTripSummaries();
    },
    onLoadFinalSummaryHistory: handleLoadFinalSummaryHistory,
    onSaveAllFinalSummaries: handleSaveAllFinalSummaries,
    syncHistoryDateSelection,
  });
}
function renderSpecificationModal() {
  if (!state.isSpecificationModalOpen) {
    const root = document.querySelector("#specification-root");
    if (root) {
      root.innerHTML = "";
    }
    return;
  }

  renderSpecificationShell();
  renderSpecificationPanel();
}

function renderSpecificationShell() {
  const root = document.querySelector("#specification-root");
  if (!root) {
    return;
  }

  if (!state.isSpecificationModalOpen) {
    root.innerHTML = "";
    return;
  }

  if (root.querySelector(".specification-modal")) {
    return;
  }

  root.innerHTML = "";
  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop";

  const card = document.createElement("section");
  card.className = "detail-card specification-modal";
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");
  card.setAttribute("aria-labelledby", "specification-title");
  card.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Manual master data";

  const title = document.createElement("h2");
  title.id = "specification-title";
  title.textContent = "Driver & Vehicle Specification";
  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "detail-close";
  closeButton.textContent = "Close";
  closeButton.addEventListener("click", closeSpecificationModal);
  header.append(titleWrap, closeButton);

  const tabs = document.createElement("div");
  tabs.id = "specification-tabs";
  tabs.className = "spec-tabs";
  [
    { id: "drivers", label: "Drivers" },
    { id: "vehicles", label: "Vehicles" },
  ].forEach((tab) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className =
      state.specificationActiveTab === tab.id ? "spec-tab spec-tab-active" : "spec-tab";
    button.textContent = tab.label;
    button.addEventListener("click", () => {
      setSpecificationTab(tab.id);
    });
    tabs.append(button);
  });

  const body = document.createElement("div");
  body.className = "spec-body";
  const error = document.createElement("p");
  error.id = "specification-error";
  error.className = "board-error";
  error.hidden = !state.specificationError;
  error.textContent = state.specificationError || "";

  const panel = document.createElement("div");
  panel.id = "specification-panel";
  panel.className = "spec-panel";
  body.append(error, panel);

  card.append(header, tabs, body);
  backdrop.append(card);
  root.append(backdrop);
}

function renderSpecificationPanel({ preserveScroll = false } = {}) {
  if (!state.isSpecificationModalOpen) {
    return;
  }

  let panel = document.querySelector("#specification-panel");
  if (!panel) {
    renderSpecificationShell();
    panel = document.querySelector("#specification-panel");
  }

  if (!panel) {
    return;
  }

  const previousScrollTop = preserveScroll ? getActiveSpecificationScrollTop() : 0;
  panel.innerHTML = "";

  const hasSpecificationData =
    state.specificationDrivers.length > 0 || state.specificationVehicles.length > 0;
  if (state.specificationLoading && !hasSpecificationData) {
    const loading = document.createElement("p");
    loading.className = "empty-board";
    loading.textContent = "Loading Driver and Vehicle specifications...";
    panel.append(loading);
  } else {
    panel.append(
      state.specificationActiveTab === "drivers"
        ? createDriverSpecificationSection()
        : createVehicleSpecificationSection(),
    );
  }

  updateSpecificationTabButtons();
  showSpecificationError(state.specificationError);

  if (preserveScroll) {
    requestAnimationFrame(() => {
      restoreActiveSpecificationScrollTop(previousScrollTop);
    });
  }
}

function setSpecificationTab(tabName) {
  state.specificationActiveTab = tabName;
  state.driverSpecificationForm = null;
  state.driverSpecificationEditingId = "";
  state.vehicleSpecificationForm = null;
  state.vehicleSpecificationEditingId = "";
  updateSpecificationTabButtons();
  renderSpecificationPanel();
}

function updateSpecificationTabButtons() {
  document.querySelectorAll("#specification-tabs .spec-tab").forEach((button) => {
    const isActive = button.textContent.toLowerCase() === state.specificationActiveTab;
    button.className = isActive ? "spec-tab spec-tab-active" : "spec-tab";
  });
}

function getActiveSpecificationScrollTop() {
  const wrap = document.querySelector(".specification-modal .spec-table-wrap");
  return wrap ? wrap.scrollTop : 0;
}

function restoreActiveSpecificationScrollTop(scrollTop) {
  const wrap = document.querySelector(".specification-modal .spec-table-wrap");
  if (wrap) {
    wrap.scrollTop = scrollTop;
  }
}

function createDriverSpecificationSection() {
  const section = document.createElement("section");
  section.className = "spec-section";

const heading = document.createElement("div");
heading.className = "spec-section-heading";
const addButton = document.createElement("button");
addButton.type = "button";
addButton.textContent = "Add Driver";
addButton.disabled = state.specificationSaving;
addButton.addEventListener("click", startAddDriverSpecification);
heading.append(addButton);
section.append(heading);

  if (state.driverSpecificationForm) {
    section.append(createDriverSpecificationForm());
  }

  const tableWrap = document.createElement("div");
  tableWrap.className = "spec-table-wrap";
  const table = document.createElement("table");
  table.className = "spec-table";
  table.append(createSpecTableHead([
    "Available",
    "Driver ID",
    "Name",
    "License No",
    "Email",
    "Phone Number",
    "Start",
    "End",
    "Pallet Only",
    "Actions",
  ]));

  const tbody = document.createElement("tbody");
  state.specificationDrivers.forEach((driver) => {
    const row = document.createElement("tr");
    row.append(
      createAvailabilityCell(driver.is_available, (checked, checkbox) =>
        handleToggleDriverAvailability(driver, checked, checkbox),
      ),
      createTextCell(driver.driver_id),
      createTextCell(driver.name),
      createTextCell(driver.license_no || ""),
      createTextCell(driver.email || ""),
      createTextCell(driver.phone_number || ""),
      createTextCell(driver.start_time || ""),
      createTextCell(driver.end_time || ""),
      createTextCell(driver.pallet_only ? "Yes" : "No"),
      createActionsCell([
        { label: "Edit", handler: () => startEditDriverSpecification(driver) },
        { label: "Delete", handler: () => handleDeleteDriverSpecification(driver.driver_id) },
      ]),
    );
    tbody.append(row);
  });
  table.append(tbody);
  tableWrap.append(table);
  section.append(tableWrap);
  return section;
}

function createVehicleSpecificationSection() {
  const section = document.createElement("section");
  section.className = "spec-section";

const heading = document.createElement("div");
heading.className = "spec-section-heading";
const addButton = document.createElement("button");
addButton.type = "button";
addButton.textContent = "Add Vehicle";
addButton.disabled = state.specificationSaving;
addButton.addEventListener("click", startAddVehicleSpecification);
heading.append(addButton);
section.append(heading);

  if (state.vehicleSpecificationForm) {
    section.append(createVehicleSpecificationForm());
  }

  const tableWrap = document.createElement("div");
  tableWrap.className = "spec-table-wrap";
  const table = document.createElement("table");
  table.className = "spec-table";
  table.append(createSpecTableHead([
    "Available",
    "Vehicle ID",
    "Rego",
    "Type",
    "Pallet Capacity",
    "Tub Capacity",
    "Trolley Capacity",
    "Stillage Capacity",
    "Actions",
  ]));

  const tbody = document.createElement("tbody");
  state.specificationVehicles.forEach((vehicle) => {
    const row = document.createElement("tr");
    row.append(
      createAvailabilityCell(vehicle.is_available, (checked, checkbox) =>
        handleToggleVehicleAvailability(vehicle, checked, checkbox),
      ),
      createTextCell(vehicle.vehicle_id),
      createTextCell(vehicle.rego),
      createTextCell(vehicle.type || ""),
      createTextCell(vehicle.pallet_capacity),
      createTextCell(vehicle.tub_capacity),
      createTextCell(vehicle.trolley_capacity),
      createTextCell(vehicle.stillage_capacity),
      createActionsCell([
        { label: "Edit", handler: () => startEditVehicleSpecification(vehicle) },
        { label: "Delete", handler: () => handleDeleteVehicleSpecification(vehicle.vehicle_id) },
      ]),
    );
    tbody.append(row);
  });
  table.append(tbody);
  tableWrap.append(table);
  section.append(tableWrap);
  return section;
}

function createDriverSpecificationForm() {
  const form = document.createElement("form");
  form.className = "spec-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handleSaveDriverSpecification();
  });

  form.append(
    createSpecInput("Name", "name", state.driverSpecificationForm, updateDriverSpecificationForm, { required: true }),
    createSpecInput("License No", "license_no", state.driverSpecificationForm, updateDriverSpecificationForm),
    createSpecInput("Email", "email", state.driverSpecificationForm, updateDriverSpecificationForm, { type: "email" }),
    createSpecInput("Phone Number", "phone_number", state.driverSpecificationForm, updateDriverSpecificationForm, { type: "tel" }),
    createSpecInput("Start Time", "start_time", state.driverSpecificationForm, updateDriverSpecificationForm, { type: "time" }),
    createSpecInput("End Time", "end_time", state.driverSpecificationForm, updateDriverSpecificationForm, { type: "time" }),
    createSpecCheckbox("Available", "is_available", state.driverSpecificationForm, updateDriverSpecificationForm),
    createSpecCheckbox("Pallet Only", "pallet_only", state.driverSpecificationForm, updateDriverSpecificationForm),
    createSpecInput("Preferred Zone", "preferred_zone", state.driverSpecificationForm, updateDriverSpecificationForm),
    createSpecFormActions(cancelDriverSpecificationForm),
  );
  return form;
}

function createVehicleSpecificationForm() {
  const form = document.createElement("form");
  form.className = "spec-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handleSaveVehicleSpecification();
  });

  form.append(
    createSpecInput("Rego", "rego", state.vehicleSpecificationForm, updateVehicleSpecificationForm, { required: true }),
    createSpecInput("Type", "type", state.vehicleSpecificationForm, updateVehicleSpecificationForm),
    createSpecCheckbox("Available", "is_available", state.vehicleSpecificationForm, updateVehicleSpecificationForm),
    createSpecInput("Pallet Capacity", "pallet_capacity", state.vehicleSpecificationForm, updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecInput("Tub Capacity", "tub_capacity", state.vehicleSpecificationForm, updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecInput("Trolley Capacity", "trolley_capacity", state.vehicleSpecificationForm, updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecInput("Stillage Capacity", "stillage_capacity", state.vehicleSpecificationForm, updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecFormActions(cancelVehicleSpecificationForm),
  );
  return form;
}

function createSpecInput(label, field, formState, updateFn, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const input = document.createElement("input");
  input.name = field;
  input.value = formState[field] ?? "";
  input.type = options.type || "text";
  input.disabled = state.specificationSaving;
  if (options.required) {
    input.required = true;
  }
  if (options.min !== undefined) {
    input.min = options.min;
  }
  input.addEventListener("input", () => {
    updateFn(field, input.value);
  });
  wrapper.append(input);
  return wrapper;
}

function createSpecCheckbox(label, field, formState, updateFn) {
  const wrapper = document.createElement("label");
  wrapper.className = "spec-checkbox";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(formState[field]);
  input.disabled = state.specificationSaving;
  input.addEventListener("change", () => {
    updateFn(field, input.checked);
  });
  wrapper.append(input, document.createTextNode(label));
  return wrapper;
}

function createSpecFormActions(cancelHandler) {
  const actions = document.createElement("div");
  actions.className = "spec-form-actions";
  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.textContent = state.specificationSaving ? "Saving..." : "Save";
  saveButton.disabled = state.specificationSaving;
  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "button-secondary";
  cancelButton.textContent = "Cancel";
  cancelButton.disabled = state.specificationSaving;
  cancelButton.addEventListener("click", cancelHandler);
  actions.append(saveButton, cancelButton);
  return actions;
}

function createSpecTableHead(labels) {
  const thead = document.createElement("thead");
  const row = document.createElement("tr");
  labels.forEach((label) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    row.append(th);
  });
  thead.append(row);
  return thead;
}

function createTextCell(value) {
  const cell = document.createElement("td");
  cell.textContent = formatOptional(value, "");
  return cell;
}

function createAvailabilityCell(isAvailable, handler) {
  const cell = document.createElement("td");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = Boolean(isAvailable);
  checkbox.disabled = state.specificationSaving;
  checkbox.addEventListener("change", () => {
    handler(checkbox.checked, checkbox);
  });
  cell.append(checkbox);
  return cell;
}

function createActionsCell(actions) {
  const cell = document.createElement("td");
  const wrap = document.createElement("div");
  wrap.className = "spec-actions";
  actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button-secondary";
    button.textContent = action.label;
    button.disabled = state.specificationSaving;
    button.addEventListener("click", action.handler);
    wrap.append(button);
  });
  cell.append(wrap);
  return cell;
}

function renderAddOrderPopup() {
  renderAddOrderPopupView({
    onCloseAddOrder: closeAddOrder,
    onCreateOrder: handleCreateOrder,
    onUpdateAddOrderForm: updateAddOrderForm,
  });
}

function renderOrderDetailPopup() {
  renderOrderDetailPopupView({
    getOrderEditForm,
    onCancelOrder: handleCancelOrder,
    onCancelOrderEdit: cancelOrderEdit,
    onCloseOrderDetail: closeOrderDetail,
    onSaveOrderEdit: handleUpdateOrder,
    onStartOrderEdit: startOrderEdit,
    onUpdateOrderEditForm: updateOrderEditForm,
  });
}
function renderBoard() {
  renderAccountStatus();
  renderBoardControls();
  renderTaskPoolFilters();
  renderTaskPool();
  renderDriverSummary();
  renderFinalTripSummaries();
  renderOrderDetailPopup();
  renderAddOrderPopup();
  renderSpecificationModal();
  renderAuthGate();
}

restoreAccountSession();
renderBoard();
loadBoard(state.dispatchDate);
loadFinalSummaryDates();






