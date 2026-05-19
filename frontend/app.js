import {
  apiGetBoard,
  apiListFinalSummaryDates,
} from "./js/api/manual-dispatch-api.js";
import { createAssignmentActions } from "./js/actions/assignment-actions.js";
import { createAuthActions } from "./js/actions/auth-actions.js";
import { createFinalSummaryActions } from "./js/actions/final-summary-actions.js";
import { createOrderActions } from "./js/actions/order-actions.js";
import { createSpecificationActions } from "./js/actions/specification-actions.js";
import { createVehicleActions } from "./js/actions/vehicle-actions.js";
import { DEFAULT_DISPATCH_DATE, state } from "./js/state/app-state.js";
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
import { renderOpShopPickupDetailPopup as renderOpShopPickupDetailPopupView } from "./js/render/opshop-pickup-modal-renderer.js";

function normalizeBoardResponse(payload) {
  return {
    dispatchDate: payload.dispatch_date || state.dispatchDate,
    orders: payload.orders || [],
    drivers: payload.drivers || [],
    vehicles: payload.vehicles || [],
    assignments: payload.assignments || [],
    opshopPickups: payload.opshop_pickups || [],
    assignedOpShopPickups: payload.assigned_opshop_pickups || [],
    driverVehicleAssignments: (payload.driver_vehicle_assignments || []).map((assignment) => ({
      ...assignment,
      delivery_date: assignment.delivery_date || assignment.dispatch_date || payload.dispatch_date || state.dispatchDate,
    })),
  };
}

function applyBoardResponse(payload) {
  const board = normalizeBoardResponse(payload);
  state.dispatchDate = board.dispatchDate;
  if (!state.driverSummaryDeliveryDate) {
    state.driverSummaryDeliveryDate = board.dispatchDate;
  }
  state.orders = board.orders;
  state.drivers = board.drivers;
  state.vehicles = board.vehicles;
  state.assignments = board.assignments;
  state.opshopPickups = board.opshopPickups;
  state.assignedOpShopPickups = board.assignedOpShopPickups;
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
    state.driverSummaryDeliveryDate = nextDate;
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
      specificationActions.openSpecificationModal();
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
    onDeliveryDateChange: (value) => {
      state.taskPoolDeliveryDateFilter = value;
      renderTaskPoolFilters();
      renderTaskPool();
    },
    onClearDeliveryDate: () => {
      state.taskPoolDeliveryDateFilter = "";
      renderTaskPoolFilters();
      renderTaskPool();
    },
  });
}

function renderTaskPool() {
  renderTaskPoolView({
    getPendingSelection: assignmentActions.getPendingSelection,
    onOpenOpShopPickupDetail: openOpShopPickupDetail,
    onOpenOrderDetail: orderActions.openOrderDetail,
    onPendingSelectionChange: assignmentActions.updatePendingSelection,
    onAssignTask: assignmentActions.handleAssignTask,
  });
}

function openOpShopPickupDetail(pickupTaskId) {
  state.activeOpShopPickupDetailId = pickupTaskId;
  renderOpShopPickupDetailPopup();
}

function closeOpShopPickupDetail() {
  state.activeOpShopPickupDetailId = "";
  renderOpShopPickupDetailPopup();
}

function renderOpShopPickupDetailPopup() {
  renderOpShopPickupDetailPopupView({
    onCloseOpShopPickupDetail: closeOpShopPickupDetail,
  });
}

function renderDriverSummary() {
  renderDriverSummaryView({
    onDeliveryDateChange: (deliveryDate) => {
      state.driverSummaryDeliveryDate = deliveryDate;
      state.finalSummaryGlobalSaveError = "";
      state.finalSummaryGlobalSaveSuccess = "";
      renderDriverSummary();
      renderFinalTripSummaries();
    },
    onVehicleChange: vehicleActions.handleVehicleChange,
    onGenerateDriverSummary: finalSummaryActions.handleGenerateDriverSummary,
    onOpenOpShopPickupDetail: openOpShopPickupDetail,
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
  closeButton.addEventListener("click", specificationActions.closeSpecificationModal);
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
  specificationActions.showSpecificationError(state.specificationError);

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
addButton.addEventListener("click", specificationActions.startAddDriverSpecification);
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
      specificationActions.handleToggleDriverAvailability(driver, checked, checkbox),
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
        { label: "Edit", handler: () => specificationActions.startEditDriverSpecification(driver) },
        { label: "Delete", handler: () => specificationActions.handleDeleteDriverSpecification(driver.driver_id) },
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
addButton.addEventListener("click", specificationActions.startAddVehicleSpecification);
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
      specificationActions.handleToggleVehicleAvailability(vehicle, checked, checkbox),
      ),
      createTextCell(vehicle.vehicle_id),
      createTextCell(vehicle.rego),
      createTextCell(vehicle.type || ""),
      createTextCell(vehicle.pallet_capacity),
      createTextCell(vehicle.tub_capacity),
      createTextCell(vehicle.trolley_capacity),
      createTextCell(vehicle.stillage_capacity),
      createActionsCell([
        { label: "Edit", handler: () => specificationActions.startEditVehicleSpecification(vehicle) },
        { label: "Delete", handler: () => specificationActions.handleDeleteVehicleSpecification(vehicle.vehicle_id) },
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
    specificationActions.handleSaveDriverSpecification();
  });

  form.append(
    createSpecInput("Name", "name", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm, { required: true }),
    createSpecInput("License No", "license_no", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm),
    createSpecInput("Email", "email", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm, { type: "email" }),
    createSpecInput("Phone Number", "phone_number", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm, { type: "tel" }),
    createSpecInput("Start Time", "start_time", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm, { type: "time" }),
    createSpecInput("End Time", "end_time", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm, { type: "time" }),
    createSpecCheckbox("Available", "is_available", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm),
    createSpecCheckbox("Pallet Only", "pallet_only", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm),
    createSpecInput("Preferred Zone", "preferred_zone", state.driverSpecificationForm, specificationActions.updateDriverSpecificationForm),
    createSpecFormActions(specificationActions.cancelDriverSpecificationForm),
  );
  return form;
}

function createVehicleSpecificationForm() {
  const form = document.createElement("form");
  form.className = "spec-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    specificationActions.handleSaveVehicleSpecification();
  });

  form.append(
    createSpecInput("Rego", "rego", state.vehicleSpecificationForm, specificationActions.updateVehicleSpecificationForm, { required: true }),
    createSpecInput("Type", "type", state.vehicleSpecificationForm, specificationActions.updateVehicleSpecificationForm),
    createSpecCheckbox("Available", "is_available", state.vehicleSpecificationForm, specificationActions.updateVehicleSpecificationForm),
    createSpecInput("Pallet Capacity", "pallet_capacity", state.vehicleSpecificationForm, specificationActions.updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecInput("Tub Capacity", "tub_capacity", state.vehicleSpecificationForm, specificationActions.updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecInput("Trolley Capacity", "trolley_capacity", state.vehicleSpecificationForm, specificationActions.updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecInput("Stillage Capacity", "stillage_capacity", state.vehicleSpecificationForm, specificationActions.updateVehicleSpecificationForm, { type: "number", min: 0 }),
    createSpecFormActions(specificationActions.cancelVehicleSpecificationForm),
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
    onAddProductLine: () => orderActions.addProductLine("add"),
    onCloseAddOrder: orderActions.closeAddOrder,
    onCreateOrder: orderActions.handleCreateOrder,
    onRemoveProductLine: (index) => orderActions.removeProductLine("add", index),
    onUpdateAddOrderForm: orderActions.updateAddOrderForm,
    onUpdateProductLine: (index, field, value) =>
      orderActions.updateProductLine("add", index, field, value),
  });
}

function renderOrderDetailPopup() {
  renderOrderDetailPopupView({
    getOrderEditForm: orderActions.getOrderEditForm,
    onAddProductLine: () => orderActions.addProductLine("edit"),
    onCancelOrder: orderActions.handleCancelOrder,
    onCancelOrderEdit: orderActions.cancelOrderEdit,
    onCloseOrderDetail: orderActions.closeOrderDetail,
    onRemoveProductLine: (index) => orderActions.removeProductLine("edit", index),
    onSaveOrderEdit: orderActions.handleUpdateOrder,
    onStartOrderEdit: orderActions.startOrderEdit,
    onToggleProductDetail: orderActions.toggleProductDetail,
    onUpdateOrderEditForm: orderActions.updateOrderEditForm,
    onUpdateProductLine: (index, field, value) =>
      orderActions.updateProductLine("edit", index, field, value),
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
  renderOpShopPickupDetailPopup();
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
  closeOpShopPickupDetail,
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

const specificationActions = createSpecificationActions({
  loadBoard,
  renderSpecificationPanel,
  renderSpecificationShell,
  state,
  updateSpecificationTabButtons,
});

authActions.restoreAccountSession();
renderBoard();
loadBoard(state.dispatchDate);
loadFinalSummaryDates();






