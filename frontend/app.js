import {
  apiCreateDriver,
  apiCreateVehicle,
  apiDeleteDriver,
  apiDeleteVehicle,
  apiGetBoard,
  apiGetSpecifications,
  apiListFinalSummaryDates,
  apiUpdateDriver,
  apiUpdateVehicle,
} from "./js/api/manual-dispatch-api.js";
import { createAssignmentActions } from "./js/actions/assignment-actions.js";
import { createAuthActions } from "./js/actions/auth-actions.js";
import { createFinalSummaryActions } from "./js/actions/final-summary-actions.js";
import { createOrderActions } from "./js/actions/order-actions.js";
import { createVehicleActions } from "./js/actions/vehicle-actions.js";
import { DEFAULT_DISPATCH_DATE, state } from "./js/state/app-state.js";
import {
  findDriverById,
  findVehicleById,
} from "./js/state/selectors.js";
import {
  formatOptional,
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
  assignmentActions.cleanupPendingSelections();
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

function renderAccountStatus() {
  renderAccountStatusView({ onLogout: authActions.logoutAccount });
}

function renderAuthGate() {
  renderAuthGateView({
    onLogin: authActions.handleLogin,
    onRegister: authActions.handleRegister,
    onResetPassword: authActions.handleResetPassword,
    onSwitchAuthMode: authActions.switchAuthMode,
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
      orderActions.openAddOrder();
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
    getPendingSelection: assignmentActions.getPendingSelection,
    onOpenOrderDetail: orderActions.openOrderDetail,
    onPendingSelectionChange: assignmentActions.updatePendingSelection,
    onAssign: assignmentActions.handleAssign,
  });
}
function renderDriverSummary() {
  renderDriverSummaryView({
    onVehicleChange: vehicleActions.handleVehicleChange,
    onGenerateDriverSummary: finalSummaryActions.handleGenerateDriverSummary,
    onOpenOrderDetail: orderActions.openOrderDetail,
    onUnassign: assignmentActions.handleUnassign,
  });
}
function renderFinalTripSummaries() {
  renderFinalTripSummariesView({
    getUnsavedFinalSummaries: finalSummaryActions.getUnsavedFinalSummaries,
    normalizeFinalSummary: finalSummaryActions.normalizeFinalSummary,
    onHistoryDateChange: (historyDate) => {
      state.historyDate = historyDate;
      state.historyLoaded = false;
      state.historyError = "";
      state.finalSummaryHistory = [];
      renderFinalTripSummaries();
    },
    onLoadFinalSummaryHistory: finalSummaryActions.handleLoadFinalSummaryHistory,
    onSaveAllFinalSummaries: finalSummaryActions.handleSaveAllFinalSummaries,
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
    onCloseAddOrder: orderActions.closeAddOrder,
    onCreateOrder: orderActions.handleCreateOrder,
    onUpdateAddOrderForm: orderActions.updateAddOrderForm,
  });
}

function renderOrderDetailPopup() {
  renderOrderDetailPopupView({
    getOrderEditForm: orderActions.getOrderEditForm,
    onCancelOrder: orderActions.handleCancelOrder,
    onCancelOrderEdit: orderActions.cancelOrderEdit,
    onCloseOrderDetail: orderActions.closeOrderDetail,
    onSaveOrderEdit: orderActions.handleUpdateOrder,
    onStartOrderEdit: orderActions.startOrderEdit,
    onUpdateOrderEditForm: orderActions.updateOrderEditForm,
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

const authActions = createAuthActions({
  renderAuthGate,
  renderBoard,
  state,
});

const orderActions = createOrderActions({
  clearError,
  loadBoard,
  renderAddOrderPopup,
  renderBoard,
  renderOrderDetailPopup,
  showError,
  state,
});

const assignmentActions = createAssignmentActions({
  clearError,
  closeOrderDetail: orderActions.closeOrderDetail,
  loadBoard,
  renderBoard,
  showError,
  state,
});

const vehicleActions = createVehicleActions({
  clearError,
  loadBoard,
  renderBoard,
  showError,
  state,
});

const finalSummaryActions = createFinalSummaryActions({
  clearError,
  loadBoard,
  loadFinalSummaryDates,
  renderBoard,
  renderFinalTripSummaries,
  showError,
  state,
});

authActions.restoreAccountSession();
renderBoard();
loadBoard(state.dispatchDate);
loadFinalSummaryDates();






