const DEFAULT_DISPATCH_DATE = "2026-05-05";
const API_BASE_URL =
  window.MANUAL_DISPATCH_API_BASE_URL ||
  (window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "");

const state = {
  dispatchDate: DEFAULT_DISPATCH_DATE,
  isLoading: false,
  isSaving: false,
  errorMessage: "",
  orders: [],
  drivers: [],
  vehicles: [],
  assignments: [],
  driverVehicleAssignments: [],
  pendingSelections: {},
  taskPoolSearch: "",
  urgencyFilter: "All",
  finalTripSummaries: {},
  generatedTaskKeys: new Set(),
  activeOrderDetailId: "",
  isAddOrderOpen: false,
  addOrderError: "",
  addOrderForm: {},
  isOrderEditMode: false,
  orderEditError: "",
  orderEditForm: {},
};

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

function formatApiErrorDetail(detail) {
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

async function apiGetBoard(dispatchDate) {
  return requestJson("/api/manual-dispatch/board", {
    query: { dispatch_date: dispatchDate },
  });
}

async function apiAssignTask(payload) {
  return requestJson("/api/manual-dispatch/assign", {
    method: "POST",
    body: payload,
  });
}

async function apiUnassignTask(payload) {
  return requestJson("/api/manual-dispatch/unassign", {
    method: "POST",
    body: payload,
  });
}

async function apiAssignDriverVehicle(payload) {
  return requestJson("/api/manual-dispatch/driver-vehicle", {
    method: "POST",
    body: payload,
  });
}

async function apiCreateOrder(payload) {
  return requestJson("/api/manual-dispatch/orders", {
    method: "POST",
    body: payload,
  });
}

async function apiUpdateOrder(orderId, payload) {
  return requestJson(`/api/manual-dispatch/orders/${encodeURIComponent(orderId)}`, {
    method: "PATCH",
    body: payload,
  });
}

async function apiCancelOrder(orderId) {
  return requestJson(`/api/manual-dispatch/orders/${encodeURIComponent(orderId)}/cancel`, {
    method: "POST",
  });
}

function getExcelExportUrl(dispatchDate) {
  return getApiUrl("/api/manual-dispatch/export-excel", {
    dispatch_date: dispatchDate,
  });
}

function getExportFilename(response, dispatchDate) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  return match ? match[1] : `manual-dispatch-${dispatchDate}.xlsx`;
}

async function loadBoard(dispatchDate = state.dispatchDate) {
  state.dispatchDate = dispatchDate || DEFAULT_DISPATCH_DATE;
  state.isLoading = true;
  state.errorMessage = "";
  renderBoard();

  try {
    const payload = await apiGetBoard(state.dispatchDate);
    applyBoardResponse(payload);
  } catch (error) {
    showError(`Unable to load board data. ${error.message}`);
  } finally {
    state.isLoading = false;
    state.isSaving = false;
    renderBoard();
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

async function handleExportExcel() {
  if (state.isLoading || state.isSaving) {
    return;
  }

  state.isSaving = true;
  clearError();
  renderBoard();

  try {
    const response = await fetch(getExcelExportUrl(state.dispatchDate));
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

    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = getExportFilename(response, state.dispatchDate);
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    showError(`Unable to export Excel. ${error.message}`);
  } finally {
    state.isSaving = false;
    renderBoard();
  }
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

function getDisplayPalletQuantity(order) {
  const palletQuantity = Number(order.pallet_quantity);
  const looseBagsQuantity = Number(order.loose_bags_quantity);

  if ((!Number.isFinite(palletQuantity) || palletQuantity === 0) && looseBagsQuantity > 0) {
    return 0;
  }

  return Number.isFinite(palletQuantity) ? palletQuantity : 0;
}

function getLooseBagsQuantity(order) {
  const looseBagsQuantity = Number(order.loose_bags_quantity);
  return Number.isFinite(looseBagsQuantity) ? looseBagsQuantity : 0;
}

function formatOptional(value, fallback = "-") {
  return value === undefined || value === null || value === "" ? fallback : value;
}

function truncateText(value, maxLength = 44) {
  const text = formatOptional(value, "");
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}...`;
}

function createOption(value, label, selected = false) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  option.selected = selected;
  return option;
}

function createBadge(text, variant = "neutral") {
  const badge = document.createElement("span");
  badge.className = `hint-badge hint-badge-${variant}`;
  badge.textContent = text;
  return badge;
}

function createHint(text, variant = "neutral") {
  const hint = document.createElement("p");
  hint.className = `hint-row hint-row-${variant}`;
  hint.textContent = text;
  return hint;
}

function createDetailField(label, value) {
  const field = document.createElement("div");
  field.className = "detail-field";

  const labelElement = document.createElement("dt");
  labelElement.textContent = label;

  const valueElement = document.createElement("dd");
  valueElement.textContent = formatOptional(value);

  field.append(labelElement, valueElement);
  return field;
}

function getAssignmentForOrder(order) {
  return state.assignments.find(
    (assignment) =>
      assignment.task_type === "ORDER" && assignment.task_id === order.order_id,
  );
}

function getTaskKey(taskType, taskId) {
  return `${taskType}:${taskId}`;
}

function isGeneratedTask(taskType, taskId) {
  return state.generatedTaskKeys.has(getTaskKey(taskType, taskId));
}

function getUnassignedOrders() {
  return state.orders.filter(
    (order) => !getAssignmentForOrder(order) && !isGeneratedTask("ORDER", order.order_id),
  );
}

function normalizeSearchText(value) {
  return String(value || "").trim().toLowerCase();
}

function orderMatchesSearch(order, searchText) {
  if (!searchText) {
    return true;
  }

  return [
    order.invoice_number,
    order.company_name,
    order.suburb,
    order.postcode,
    order.note,
  ].some((value) => normalizeSearchText(value).includes(searchText));
}

function orderMatchesUrgencyFilter(order) {
  if (state.urgencyFilter === "All") {
    return true;
  }
  return getUrgencyLabel(order) === state.urgencyFilter;
}

function getFilteredUnassignedOrders() {
  const searchText = normalizeSearchText(state.taskPoolSearch);
  return getUnassignedOrders().filter(
    (order) => orderMatchesSearch(order, searchText) && orderMatchesUrgencyFilter(order),
  );
}

function getOrderByTaskId(taskId) {
  return state.orders.find((order) => order.order_id === taskId);
}

function findDriverById(driverId) {
  return state.drivers.find((driver) => driver.driver_id === driverId);
}

function findVehicleById(vehicleId) {
  return state.vehicles.find((vehicle) => vehicle.vehicle_id === vehicleId);
}

function getDriverVehicleAssignment(driverId) {
  return state.driverVehicleAssignments.find(
    (assignment) =>
      assignment.dispatch_date === state.dispatchDate && assignment.driver_id === driverId,
  );
}

function getSelectedVehicleForDriver(driverId) {
  const assignment = getDriverVehicleAssignment(driverId);
  return assignment ? findVehicleById(assignment.vehicle_id) : null;
}

function isVehicleSelectedByAnotherDriver(driverId, vehicleId) {
  if (!vehicleId) {
    return false;
  }

  return state.driverVehicleAssignments.some(
    (assignment) =>
      assignment.dispatch_date === state.dispatchDate &&
      assignment.driver_id !== driverId &&
      assignment.vehicle_id === vehicleId,
  );
}

function getOrderPreferredDriverName(order) {
  const driver = order.preferred_driver_id ? findDriverById(order.preferred_driver_id) : null;
  return driver ? driver.name : "";
}

function isUrgent(order) {
  return String(order.urgency || "").toLowerCase() === "urgent";
}

function getUrgencyLabel(order) {
  const urgency = order.urgency || "Normal";
  return urgency.charAt(0).toUpperCase() + urgency.slice(1).toLowerCase();
}

function getAssignedOrdersForDriver(driverId) {
  return state.assignments
    .filter((assignment) => assignment.driver_id === driverId)
    .map((assignment) => getOrderByTaskId(assignment.task_id))
    .filter(Boolean);
}

function getAssignedOrdersForTrip(driverId, tripNo) {
  return state.assignments
    .filter((assignment) => assignment.driver_id === driverId && assignment.trip_no === tripNo)
    .map((assignment) => getOrderByTaskId(assignment.task_id))
    .filter(Boolean);
}

function getAssignmentsForDriver(driverId) {
  return state.assignments.filter(
    (assignment) =>
      assignment.driver_id === driverId &&
      (!assignment.dispatch_date || assignment.dispatch_date === state.dispatchDate),
  );
}

function getAssignmentsForDriverTrip(driverId, tripNo) {
  return getAssignmentsForDriver(driverId).filter((assignment) => assignment.trip_no === tripNo);
}

function calculateTotals(orders) {
  return orders.reduce(
    (totals, order) => ({
      pallets: totals.pallets + getDisplayPalletQuantity(order),
      looseBags: totals.looseBags + getLooseBagsQuantity(order),
    }),
    { pallets: 0, looseBags: 0 },
  );
}

function calculateDriverTotals(driverId) {
  return calculateTotals(getAssignedOrdersForDriver(driverId));
}

function calculateTripTotals(driverId, tripNo) {
  return calculateTotals(getAssignedOrdersForTrip(driverId, tripNo));
}

function isVehicleCapacityExceeded(driverId) {
  const selectedVehicle = getSelectedVehicleForDriver(driverId);
  if (!selectedVehicle) {
    return false;
  }

  return calculateDriverTotals(driverId).pallets > Number(selectedVehicle.pallet_capacity || 0);
}

function getDriverExceptions(driver) {
  const messages = [];
  const assignedOrders = getAssignedOrdersForDriver(driver.driver_id);

  if (driver.pallet_only && assignedOrders.some((order) => getLooseBagsQuantity(order) > 0)) {
    messages.push("Exception: Driver only handles pallet orders");
  }

  if (isVehicleCapacityExceeded(driver.driver_id)) {
    messages.push("Exception: Assigned pallets exceed selected vehicle capacity");
  }

  return messages;
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
            company_name: order.company_name || "",
            suburb: order.suburb || "",
            invoice_number: order.invoice_number || "",
            pallet_quantity: getDisplayPalletQuantity(order),
            loose_bags_quantity: getLooseBagsQuantity(order),
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
    vehicle_rego: selectedVehicle ? selectedVehicle.rego : "No vehicle selected",
    total_pallets: allOrders.reduce((total, order) => total + Number(order.pallet_quantity || 0), 0),
    total_loose_bags: allOrders.reduce((total, order) => total + Number(order.loose_bags_quantity || 0), 0),
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

function renderBoardControls() {
  const dateInput = document.querySelector("#dispatch-date");
  const exportButton = document.querySelector("#export-excel-button");
  const addOrderButton = document.querySelector("#add-order-button");
  const status = document.querySelector("#board-status");
  const error = document.querySelector("#board-error");

  if (!dateInput || !exportButton) {
    return;
  }

  dateInput.value = state.dispatchDate;
  dateInput.disabled = state.isLoading || state.isSaving;

  exportButton.disabled = state.isLoading || state.isSaving;
  exportButton.textContent = state.isSaving ? "Preparing..." : "Export Excel";

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
    loadBoard(nextDate);
  };

  exportButton.onclick = () => {
    handleExportExcel();
  };

  if (addOrderButton) {
    addOrderButton.onclick = () => {
      openAddOrder();
    };
  }
}

function renderTaskPoolFilters() {
  const searchInput = document.querySelector("#order-search");
  const urgencyFilter = document.querySelector("#urgency-filter");
  const summary = document.querySelector("#task-filter-summary");

  if (!searchInput || !urgencyFilter || !summary) {
    return;
  }

  const unassignedCount = getUnassignedOrders().length;
  const filteredCount = getFilteredUnassignedOrders().length;

  searchInput.value = state.taskPoolSearch;
  searchInput.disabled = state.isLoading || state.isSaving;
  urgencyFilter.value = state.urgencyFilter;
  urgencyFilter.disabled = state.isLoading || state.isSaving;
  summary.textContent =
    state.taskPoolSearch || state.urgencyFilter !== "All"
      ? `${filteredCount} of ${unassignedCount} unassigned Orders shown`
      : `${unassignedCount} unassigned Orders`;

  searchInput.oninput = () => {
    state.taskPoolSearch = searchInput.value;
    renderTaskPoolFilters();
    renderTaskPool();
  };

  urgencyFilter.onchange = () => {
    state.urgencyFilter = urgencyFilter.value || "All";
    renderTaskPoolFilters();
    renderTaskPool();
  };
}

function renderTaskPool() {
  const taskPoolList = document.querySelector("#task-pool-list");
  taskPoolList.innerHTML = "";

  if (state.isLoading && state.orders.length === 0) {
    const loadingState = document.createElement("p");
    loadingState.className = "empty-board";
    loadingState.textContent = "Loading Orders from backend...";
    taskPoolList.append(loadingState);
    return;
  }

  if (state.errorMessage && state.orders.length === 0) {
    const errorState = document.createElement("p");
    errorState.className = "empty-board";
    errorState.textContent = "Board data is unavailable. Use Retry after the backend is running.";
    taskPoolList.append(errorState);
    return;
  }

  const unassignedOrders = getUnassignedOrders();
  const filteredOrders = getFilteredUnassignedOrders();

  if (unassignedOrders.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = "No unassigned Orders available in the Task Pool.";
    taskPoolList.append(emptyState);
    return;
  }

  if (filteredOrders.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = "No matching unassigned orders.";
    taskPoolList.append(emptyState);
    return;
  }

  filteredOrders.forEach((order) => {
    const selection = getPendingSelection(order.order_id);
    const card = document.createElement("article");
    card.className = "order-card order-card-compact";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `View details for ${order.invoice_number || order.order_id}`);
    card.addEventListener("click", () => openOrderDetail(order.order_id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openOrderDetail(order.order_id);
      }
    });

    const content = document.createElement("div");
    content.className = "compact-order-main";

    const invoice = document.createElement("p");
    invoice.className = "compact-invoice";
    invoice.textContent = `Invoice # ${formatOptional(order.invoice_number)}`;

    const company = document.createElement("p");
    company.className = "compact-company";
    company.textContent = formatOptional(order.company_name);

    const suburb = document.createElement("h3");
    suburb.className = "compact-suburb";
    suburb.textContent = formatOptional(order.suburb);

    const meta = document.createElement("div");
    meta.className = "compact-meta";
    meta.append(
      createBadge(`Pallet: ${getDisplayPalletQuantity(order)}`),
      createBadge(getUrgencyLabel(order), isUrgent(order) ? "urgent" : "neutral"),
      createBadge(`Start: ${formatOptional(order.start_time)}`),
    );

    const note = document.createElement("p");
    note.className = "compact-note";
    note.textContent = `Note: ${truncateText(order.note || "None")}`;

    content.append(invoice, company, suburb, meta, note);

    const controls = document.createElement("div");
    controls.className = "order-controls compact-order-controls";
    controls.addEventListener("click", (event) => event.stopPropagation());
    controls.addEventListener("keydown", (event) => event.stopPropagation());

    const driverLabel = document.createElement("label");
    driverLabel.textContent = "Driver";
    driverLabel.setAttribute("for", `driver-${order.order_id}`);

    const driverSelect = document.createElement("select");
    driverSelect.id = `driver-${order.order_id}`;
    driverSelect.disabled = state.isSaving || state.isLoading;
    driverSelect.append(createOption("", "Select driver", selection.driver_id === ""));
    state.drivers.forEach((driver) => {
      driverSelect.append(createOption(driver.driver_id, driver.name, selection.driver_id === driver.driver_id));
    });

    const tripLabel = document.createElement("label");
    tripLabel.textContent = "Trip";
    tripLabel.setAttribute("for", `trip-${order.order_id}`);

    const tripSelect = document.createElement("select");
    tripSelect.id = `trip-${order.order_id}`;
    tripSelect.disabled = state.isSaving || state.isLoading;
    tripSelect.append(createOption("trip1", "trip1", selection.trip_no !== "trip2"));
    tripSelect.append(createOption("trip2", "trip2", selection.trip_no === "trip2"));

    const assignButton = document.createElement("button");
    assignButton.type = "button";
    assignButton.disabled = !selection.driver_id || state.isSaving || state.isLoading;
    assignButton.textContent = state.isSaving ? "Saving..." : "Assign";
    assignButton.title = selection.driver_id
      ? "Assign this Order to the selected Driver and Trip"
      : "Select a driver to enable Assign";

    driverSelect.addEventListener("change", () => {
      updatePendingSelection(order.order_id, { driver_id: driverSelect.value });
      assignButton.disabled = driverSelect.value === "" || state.isSaving || state.isLoading;
      assignButton.title = driverSelect.value
        ? "Assign this Order to the selected Driver and Trip"
        : "Select a driver to enable Assign";
    });

    tripSelect.addEventListener("change", () => {
      updatePendingSelection(order.order_id, { trip_no: tripSelect.value || "trip1" });
    });

    assignButton.addEventListener("click", (event) => {
      event.stopPropagation();
      handleAssign(order.order_id);
    });

    controls.append(driverLabel, driverSelect, tripLabel, tripSelect, assignButton);
    card.append(content, controls);
    taskPoolList.append(card);
  });
}

function renderDriverSummary() {
  const driverSummaryList = document.querySelector("#driver-summary-list");
  driverSummaryList.innerHTML = "";

  if (state.isLoading && state.drivers.length === 0) {
    const loadingState = document.createElement("p");
    loadingState.className = "empty-board";
    loadingState.textContent = "Loading Drivers from backend...";
    driverSummaryList.append(loadingState);
    return;
  }

  if (state.errorMessage && state.drivers.length === 0) {
    const errorState = document.createElement("p");
    errorState.className = "empty-board";
    errorState.textContent = "Trip Summary is unavailable until backend data loads.";
    driverSummaryList.append(errorState);
    return;
  }

  state.drivers.forEach((driver) => {
    const card = document.createElement("article");
    card.className = "driver-card trip-summary-card";

    const header = document.createElement("div");
    header.className = "driver-card-header";

    const name = document.createElement("h3");
    name.textContent = driver.name;

    const driverBadges = document.createElement("div");
    driverBadges.className = "hint-badge-row";
    driverBadges.append(
      createBadge(driver.is_available ? "Available" : "Not available", driver.is_available ? "good" : "warning"),
    );
    if (driver.pallet_only) {
      driverBadges.append(createBadge("Pallet-only driver", "warning"));
    }

    const assignedOrders = getAssignedOrdersForDriver(driver.driver_id);
    const hasLockedFinalSummary = Boolean(state.finalTripSummaries[driver.driver_id]);
    const driverTotals = calculateTotals(assignedOrders);
    const loadSummary = document.createElement("div");
    loadSummary.className = "load-summary";
    loadSummary.append(
      createHint(`Total pallets assigned: ${driverTotals.pallets}`),
      createHint(`Total loose bags assigned: ${driverTotals.looseBags}`),
    );

    const selectedVehicle = getSelectedVehicleForDriver(driver.driver_id);

    const vehicleWrap = document.createElement("label");
    vehicleWrap.className = "vehicle-select";
    vehicleWrap.textContent = "Choose Vehicle";

    const vehicleSelect = document.createElement("select");
    vehicleSelect.disabled = state.isSaving || state.isLoading;
    vehicleSelect.append(createOption("", "Select vehicle", !selectedVehicle));
    state.vehicles.forEach((vehicle) => {
      vehicleSelect.append(
        createOption(
          vehicle.vehicle_id,
          vehicle.rego,
          selectedVehicle ? selectedVehicle.vehicle_id === vehicle.vehicle_id : false,
        ),
      );
    });

    const vehicleStatus = document.createElement("p");
    vehicleStatus.className = "vehicle-status";
    vehicleStatus.textContent = selectedVehicle
      ? `Selected Vehicle: ${selectedVehicle.rego}`
      : "No vehicle selected";

    const vehicleCapacity = document.createElement("p");
    vehicleCapacity.className = "vehicle-status vehicle-capacity";
    vehicleCapacity.textContent = selectedVehicle
      ? `Capacity: ${selectedVehicle.pallet_capacity} pallets`
      : "Capacity: select a vehicle to view";

    const duplicateHint = document.createElement("p");
    duplicateHint.className = "vehicle-hint";
    duplicateHint.textContent =
      selectedVehicle && isVehicleSelectedByAnotherDriver(driver.driver_id, selectedVehicle.vehicle_id)
        ? "Vehicle also selected by another driver."
        : "";

    const exceptions = getDriverExceptions(driver);
    const exceptionList = document.createElement("div");
    exceptionList.className = "exception-list";
    exceptions.forEach((message) => {
      const item = document.createElement("p");
      item.className = "exception-item";
      item.textContent = message;
      exceptionList.append(item);
    });

    const finalLockHint = document.createElement("p");
    finalLockHint.className = "vehicle-hint final-lock-hint";
    finalLockHint.textContent = hasLockedFinalSummary
      ? "Final Trip Summary for this driver is already generated and locked."
      : "";

    const generateButton = document.createElement("button");
    generateButton.type = "button";
    generateButton.className = "button-secondary generate-summary-button";
    generateButton.textContent = state.isSaving ? "Generating..." : "Generate";
    generateButton.disabled = state.isSaving || state.isLoading;
    generateButton.addEventListener("click", () => {
      handleGenerateDriverSummary(driver.driver_id);
    });

    vehicleSelect.addEventListener("change", () => {
      handleVehicleChange(driver.driver_id, vehicleSelect.value);
    });

    vehicleWrap.append(vehicleSelect);
    header.append(name, driverBadges, loadSummary, vehicleWrap, vehicleStatus, vehicleCapacity);
    if (duplicateHint.textContent) {
      header.append(duplicateHint);
    }
    if (exceptions.length > 0) {
      header.append(exceptionList);
    }
    if (assignedOrders.length > 0 && !hasLockedFinalSummary) {
      header.append(generateButton);
    }
    if (finalLockHint.textContent) {
      header.append(finalLockHint);
    }

    const trips = document.createElement("div");
    trips.className = "trip-columns";
    if (assignedOrders.length === 0) {
      const emptyState = document.createElement("p");
      emptyState.className = "empty-trip editable-empty-state";
      emptyState.textContent = hasLockedFinalSummary
        ? "No editable tasks. Locked Final Trip Summary is shown below."
        : "No editable tasks assigned to this driver.";
      trips.append(emptyState);
    } else {
      ["trip1", "trip2"].forEach((tripNo) => {
        if (getAssignmentsForDriverTrip(driver.driver_id, tripNo).length > 0) {
          trips.append(createTripGroup(driver.driver_id, tripNo, tripNo === "trip1" ? "Trip 1" : "Trip 2"));
        }
      });
    }

    card.append(header, trips);
    driverSummaryList.append(card);
  });
}

function createTripGroup(driverId, tripNo, title) {
  const group = document.createElement("section");
  group.className = "trip-group";

  const heading = document.createElement("h4");
  heading.textContent = title;

  const tripTotals = calculateTripTotals(driverId, tripNo);
  const tripSummary = document.createElement("p");
  tripSummary.className = "trip-summary";
  tripSummary.textContent = `Pallets: ${tripTotals.pallets} | Loose bags: ${tripTotals.looseBags}`;

  const assignedTasks = state.assignments.filter(
    (assignment) => assignment.driver_id === driverId && assignment.trip_no === tripNo,
  );

  const taskList = document.createElement("div");
  taskList.className = "assigned-task-list";

  if (assignedTasks.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-trip";
    emptyState.textContent = "No tasks assigned to this trip.";
    taskList.append(emptyState);
  } else {
    assignedTasks.forEach((assignment) => {
      const order = getOrderByTaskId(assignment.task_id);
      if (!order) {
        return;
      }

      taskList.append(createAssignedTask(assignment, order));
    });
  }

  group.append(heading, tripSummary, taskList);
  return group;
}

function createAssignedTask(assignment, order) {
  const row = document.createElement("article");
  row.className = "assigned-task";
  row.tabIndex = 0;
  row.setAttribute("role", "button");
  row.setAttribute("title", "View order details");
  row.setAttribute(
    "aria-label",
    `View details for ${order.invoice_number || order.order_id}, ${order.suburb}, Pallet ${getDisplayPalletQuantity(order)}`,
  );
  row.addEventListener("click", () => openOrderDetail(order.order_id));
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openOrderDetail(order.order_id);
    }
  });

  const details = document.createElement("div");

  const suburb = document.createElement("p");
  suburb.className = "assigned-suburb";
  suburb.textContent = order.suburb;

  const pallet = document.createElement("p");
  pallet.className = "assigned-pallet";
  pallet.textContent = `Pallet: ${getDisplayPalletQuantity(order)} | Loose bags: ${getLooseBagsQuantity(order)}`;

  details.append(suburb, pallet);

  const unassignButton = document.createElement("button");
  unassignButton.type = "button";
  unassignButton.className = "button-secondary";
  unassignButton.disabled = state.isSaving || state.isLoading;
  unassignButton.textContent = state.isSaving ? "Saving..." : "Unassign";
  unassignButton.addEventListener("click", (event) => {
    event.stopPropagation();
    handleUnassign(assignment.task_type, assignment.task_id);
  });
  unassignButton.addEventListener("keydown", (event) => {
    event.stopPropagation();
  });

  row.append(details, unassignButton);
  return row;
}

function formatGeneratedAt(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function renderFinalTripSummaries() {
  const finalSummaryList = document.querySelector("#final-trip-summary-list");
  if (!finalSummaryList) {
    return;
  }

  finalSummaryList.innerHTML = "";
  const summaries = Object.values(state.finalTripSummaries);

  if (summaries.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = "No locked Final Trip Summary snapshots generated in this session.";
    finalSummaryList.append(emptyState);
    return;
  }

  summaries
    .sort((first, second) => first.driver_name.localeCompare(second.driver_name))
    .forEach((summary) => {
      finalSummaryList.append(createFinalTripSummaryCard(summary));
    });
}

function createFinalTripSummaryCard(summary) {
  const card = document.createElement("article");
  card.className = "final-summary-card";

  const header = document.createElement("div");
  header.className = "final-summary-header";

  const titleWrap = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Locked snapshot";

  const title = document.createElement("h3");
  title.textContent = summary.driver_name;

  titleWrap.append(kicker, title);

  const lockedBadge = createBadge("Locked", "good");
  header.append(titleWrap, lockedBadge);

  const meta = document.createElement("dl");
  meta.className = "final-summary-meta";
  meta.append(
    createDetailField("Date", summary.dispatch_date),
    createDetailField("Driver", summary.driver_name),
    createDetailField("Rego #", summary.vehicle_rego),
    createDetailField("Generated At", formatGeneratedAt(summary.generated_at)),
    createDetailField("Total Pallets", summary.total_pallets),
    createDetailField("Total Loose Bags", summary.total_loose_bags),
  );

  const trips = document.createElement("div");
  trips.className = "final-summary-trips";

  let rowNumber = 1;
  summary.trips.forEach((trip) => {
    if (trip.orders.length === 0) {
      return;
    }

    const tripSection = document.createElement("section");
    tripSection.className = "final-trip-section";

    const heading = document.createElement("h4");
    heading.textContent = trip.trip_no === "trip1" ? "Trip 1" : "Trip 2";

    const table = document.createElement("table");
    table.className = "final-trip-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    ["No.", "Customer Name", "Suburb", "Invoice #", "Product", "Pallets"].forEach((label) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      headerRow.append(th);
    });
    thead.append(headerRow);

    const tbody = document.createElement("tbody");
    trip.orders.forEach((order) => {
      const row = document.createElement("tr");
      [
        rowNumber,
        formatOptional(order.company_name, ""),
        formatOptional(order.suburb, ""),
        formatOptional(order.invoice_number, ""),
        "",
        order.pallet_quantity,
      ].forEach((value) => {
        const td = document.createElement("td");
        td.textContent = value;
        row.append(td);
      });
      tbody.append(row);
      rowNumber += 1;
    });

    table.append(thead, tbody);
    tripSection.append(heading, table);
    trips.append(tripSection);
  });

  card.append(header, meta, trips);
  return card;
}

function createAddOrderField(label, field, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = options.wide ? "form-field form-field-wide" : "form-field";
  wrapper.textContent = label;

  const input = document.createElement(options.multiline ? "textarea" : "input");
  input.name = field;
  input.value = state.addOrderForm[field] ?? "";
  input.disabled = state.isSaving;
  if (!options.multiline) {
    input.type = options.type || "text";
  }
  if (options.required) {
    input.required = true;
  }
  if (options.min !== undefined) {
    input.min = options.min;
  }
  input.addEventListener("input", () => {
    updateAddOrderForm(field, input.value);
  });

  wrapper.append(input);
  return wrapper;
}

function createAddOrderSelect(label, field, options) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const select = document.createElement("select");
  select.name = field;
  select.disabled = state.isSaving;
  options.forEach((option) => {
    select.append(createOption(option.value, option.label, state.addOrderForm[field] === option.value));
  });
  select.addEventListener("change", () => {
    updateAddOrderForm(field, select.value);
  });

  wrapper.append(select);
  return wrapper;
}

function createOrderEditField(label, field, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = options.wide ? "form-field form-field-wide" : "form-field";
  wrapper.textContent = label;

  const input = document.createElement(options.multiline ? "textarea" : "input");
  input.name = field;
  input.value = state.orderEditForm[field] ?? "";
  input.disabled = state.isSaving;
  if (!options.multiline) {
    input.type = options.type || "text";
  }
  if (options.required) {
    input.required = true;
  }
  if (options.min !== undefined) {
    input.min = options.min;
  }
  input.addEventListener("input", () => {
    updateOrderEditForm(field, input.value);
  });

  wrapper.append(input);
  return wrapper;
}

function createOrderEditReadOnlyField(label, value) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const input = document.createElement("input");
  input.type = "text";
  input.value = formatOptional(value);
  input.disabled = true;

  wrapper.append(input);
  return wrapper;
}

function createOrderEditSelect(label, field, options) {
  const wrapper = document.createElement("label");
  wrapper.className = "form-field";
  wrapper.textContent = label;

  const select = document.createElement("select");
  select.name = field;
  select.disabled = state.isSaving;
  options.forEach((option) => {
    select.append(createOption(option.value, option.label, state.orderEditForm[field] === option.value));
  });
  select.addEventListener("change", () => {
    updateOrderEditForm(field, select.value);
  });

  wrapper.append(select);
  return wrapper;
}

function createOrderEditForm(order) {
  const form = document.createElement("form");
  form.className = "order-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handleUpdateOrder(order.order_id);
  });

  const formGrid = document.createElement("div");
  formGrid.className = "form-grid";

  const preferredDriverOptions = [
    { value: "", label: "No preferred driver" },
    ...state.drivers.map((driver) => ({
      value: driver.driver_id,
      label: driver.name,
    })),
  ];

  formGrid.append(
    createOrderEditField("Invoice #", "invoice_number"),
    createOrderEditField("Company Name", "company_name"),
    createOrderEditField("Phone", "phone", { type: "tel" }),
    createOrderEditField("Delivery Address", "delivery_address"),
    createOrderEditField("Suburb", "suburb", { required: true }),
    createOrderEditField("Postcode", "postcode"),
    createOrderEditReadOnlyField("Delivery Date (read-only)", order.delivery_date),
    createOrderEditField("Zone", "zone"),
    createOrderEditSelect("Urgency", "urgency", [
      { value: "Normal", label: "Normal" },
      { value: "Urgent", label: "Urgent" },
    ]),
    createOrderEditSelect("Preferred Driver", "preferred_driver_id", preferredDriverOptions),
    createOrderEditField("Pallet Quantity", "pallet_quantity", {
      type: "number",
      min: "0",
    }),
    createOrderEditField("Loose Bags Quantity", "loose_bags_quantity", {
      type: "number",
      min: "0",
    }),
    createOrderEditField("Start Time", "start_time", { type: "time" }),
    createOrderEditField("End Time", "end_time", { type: "time" }),
    createOrderEditField("Note", "note", { multiline: true, wide: true }),
  );

  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.orderEditError;
  error.textContent = state.orderEditError;

  const actions = document.createElement("div");
  actions.className = "form-actions";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "button-secondary";
  cancelButton.textContent = "Cancel Edit";
  cancelButton.disabled = state.isSaving;
  cancelButton.addEventListener("click", cancelOrderEdit);

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.textContent = state.isSaving ? "Saving..." : "Save Changes";
  saveButton.disabled = state.isSaving;

  actions.append(cancelButton, saveButton);
  form.append(formGrid, error, actions);
  return form;
}

function renderAddOrderPopup() {
  const root = document.querySelector("#add-order-root");
  if (!root) {
    return;
  }

  root.innerHTML = "";
  if (!state.isAddOrderOpen) {
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop";
  backdrop.addEventListener("click", () => {
    if (!state.isSaving) {
      closeAddOrder();
    }
  });

  const modal = document.createElement("article");
  modal.className = "order-detail-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "add-order-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Manual entry";

  const title = document.createElement("h2");
  title.id = "add-order-title";
  title.textContent = "Add New Order";

  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  closeButton.textContent = "Cancel";
  closeButton.disabled = state.isSaving;
  closeButton.addEventListener("click", closeAddOrder);

  header.append(titleWrap, closeButton);

  const form = document.createElement("form");
  form.className = "order-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handleCreateOrder();
  });

  const formGrid = document.createElement("div");
  formGrid.className = "form-grid";

  const preferredDriverOptions = [
    { value: "", label: "No preferred driver" },
    ...state.drivers.map((driver) => ({
      value: driver.driver_id,
      label: driver.name,
    })),
  ];

  formGrid.append(
    createAddOrderField("Invoice #", "invoice_number"),
    createAddOrderField("Company Name", "company_name"),
    createAddOrderField("Phone", "phone", { type: "tel" }),
    createAddOrderField("Delivery Address", "delivery_address"),
    createAddOrderField("Suburb", "suburb", { required: true }),
    createAddOrderField("Postcode", "postcode"),
    createAddOrderField("Delivery Date", "delivery_date", {
      type: "date",
      required: true,
    }),
    createAddOrderField("Zone", "zone"),
    createAddOrderSelect("Urgency", "urgency", [
      { value: "Normal", label: "Normal" },
      { value: "Urgent", label: "Urgent" },
    ]),
    createAddOrderSelect("Preferred Driver", "preferred_driver_id", preferredDriverOptions),
    createAddOrderField("Pallet Quantity", "pallet_quantity", {
      type: "number",
      min: "0",
    }),
    createAddOrderField("Loose Bags Quantity", "loose_bags_quantity", {
      type: "number",
      min: "0",
    }),
    createAddOrderField("Start Time", "start_time", { type: "time" }),
    createAddOrderField("End Time", "end_time", { type: "time" }),
    createAddOrderField("Note", "note", { multiline: true, wide: true }),
  );

  const error = document.createElement("p");
  error.className = "board-error";
  error.hidden = !state.addOrderError;
  error.textContent = state.addOrderError;

  const actions = document.createElement("div");
  actions.className = "form-actions";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.className = "button-secondary";
  cancelButton.textContent = "Cancel";
  cancelButton.disabled = state.isSaving;
  cancelButton.addEventListener("click", closeAddOrder);

  const saveButton = document.createElement("button");
  saveButton.type = "submit";
  saveButton.textContent = state.isSaving ? "Saving..." : "Save Order";
  saveButton.disabled = state.isSaving;

  actions.append(cancelButton, saveButton);
  form.append(formGrid, error, actions);
  modal.append(header, form);
  backdrop.append(modal);
  root.append(backdrop);
}

function renderOrderDetailPopup() {
  let root = document.querySelector("#order-detail-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "order-detail-root";
    document.body.append(root);
  }

  root.innerHTML = "";
  if (!state.activeOrderDetailId) {
    return;
  }

  const order = getOrderByTaskId(state.activeOrderDetailId);
  if (!order) {
    state.activeOrderDetailId = "";
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop";
  backdrop.addEventListener("click", closeOrderDetail);

  const modal = document.createElement("article");
  modal.className = "order-detail-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "order-detail-title");
  modal.addEventListener("click", (event) => event.stopPropagation());

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Order details";

  const title = document.createElement("h2");
  title.id = "order-detail-title";
  title.textContent = `${formatOptional(order.invoice_number)} - ${formatOptional(order.suburb)}`;

  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  closeButton.textContent = "Close";
  closeButton.addEventListener("click", closeOrderDetail);

  const headerActions = document.createElement("div");
  headerActions.className = "detail-actions";

  if (!state.isOrderEditMode) {
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => startOrderEdit(order));

    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "button-danger";
    cancelButton.textContent = state.isSaving ? "Cancelling..." : "Cancel Order";
    cancelButton.disabled = state.isSaving;
    cancelButton.addEventListener("click", () => handleCancelOrder(order.order_id));

    headerActions.append(editButton, cancelButton);
  }

  headerActions.append(closeButton);

  header.append(titleWrap, headerActions);

  if (state.isOrderEditMode && Object.keys(state.orderEditForm).length === 0) {
    state.orderEditForm = getOrderEditForm(order);
  }

  if (state.isOrderEditMode) {
    modal.append(header, createOrderEditForm(order));
    backdrop.append(modal);
    root.append(backdrop);
    return;
  }

  const details = document.createElement("dl");
  details.className = "detail-grid";
  details.append(
    createDetailField("Order ID", order.order_id),
    createDetailField("Invoice #", order.invoice_number),
    createDetailField("Company Name", order.company_name),
    createDetailField("Phone", order.phone),
    createDetailField("Delivery Address", order.delivery_address),
    createDetailField("Suburb", order.suburb),
    createDetailField("Postcode", order.postcode),
    createDetailField("Delivery Date", order.delivery_date),
    createDetailField("Zone", order.zone),
    createDetailField("Urgency", getUrgencyLabel(order)),
    createDetailField("Preferred Driver", getOrderPreferredDriverName(order)),
    createDetailField("Pallet Quantity", getDisplayPalletQuantity(order)),
    createDetailField("Loose Bags Quantity", getLooseBagsQuantity(order)),
    createDetailField("Start Time", order.start_time),
    createDetailField("End Time", order.end_time),
    createDetailField("Note", order.note),
  );

  const detailError = document.createElement("p");
  detailError.className = "board-error";
  detailError.hidden = !state.errorMessage;
  detailError.textContent = state.errorMessage;

  modal.append(header, detailError, details);
  backdrop.append(modal);
  root.append(backdrop);
}

function renderBoard() {
  renderBoardControls();
  renderTaskPoolFilters();
  renderTaskPool();
  renderDriverSummary();
  renderFinalTripSummaries();
  renderOrderDetailPopup();
  renderAddOrderPopup();
}

renderBoard();
loadBoard(state.dispatchDate);
