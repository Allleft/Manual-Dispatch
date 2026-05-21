import { state } from "../state/app-state.js";
import {
  getFilteredUnassignedOrders,
  getUnassignedOrders,
} from "../state/selectors.js";
import {
  createBadge,
  createOption,
} from "../utils/dom-utils.js";
import {
  formatOptional,
  formatOrderLoadQuantity,
  getUrgencyLabel,
  isUrgent,
  truncateText,
} from "../utils/format-utils.js";

export function renderTaskPoolFilters({
  onSearchChange,
  onUrgencyChange,
  onDeliveryDateChange,
  onClearDeliveryDate,
}) {
  const searchInput = document.querySelector("#order-search");
  const urgencyFilter = document.querySelector("#urgency-filter");
  const deliveryDateFilter = document.querySelector("#task-pool-delivery-date-filter");
  const clearDeliveryDateFilter = document.querySelector("#clear-task-pool-delivery-date-filter");
  const summary = document.querySelector("#task-filter-summary");

  if (!searchInput || !urgencyFilter || !deliveryDateFilter || !clearDeliveryDateFilter || !summary) {
    return;
  }

  const unassignedCount = getUnassignedOrders().length;
  const filteredCount = getFilteredUnassignedOrders().length;

  searchInput.value = state.taskPoolSearch;
  searchInput.disabled = state.isLoading || state.isSaving;
  urgencyFilter.value = state.urgencyFilter;
  urgencyFilter.disabled = state.isLoading || state.isSaving;
  deliveryDateFilter.value = state.taskPoolDeliveryDateFilter;
  deliveryDateFilter.disabled = state.isLoading || state.isSaving;
  clearDeliveryDateFilter.disabled =
    state.isLoading || state.isSaving || !state.taskPoolDeliveryDateFilter;
  summary.textContent =
    state.taskPoolSearch || state.urgencyFilter !== "All" || state.taskPoolDeliveryDateFilter
      ? `${filteredCount} of ${unassignedCount} unassigned Orders shown`
      : `${unassignedCount} unassigned Orders`;

  searchInput.oninput = () => {
    onSearchChange(searchInput.value);
  };

  urgencyFilter.onchange = () => {
    onUrgencyChange(urgencyFilter.value || "All");
  };

  deliveryDateFilter.onchange = () => {
    onDeliveryDateChange(deliveryDateFilter.value || "");
  };

  clearDeliveryDateFilter.onclick = () => {
    onClearDeliveryDate();
  };
}

export function renderTaskPool({
  getPendingSelection,
  onExportOpShopRunSheet,
  onOpenOncallOpShopPickupList,
  onOpenOpShopPickupList,
  onOpenOrderDetail,
  onPendingSelectionChange,
  onAssignTask,
}) {
  const taskPoolList = document.querySelector("#task-pool-list");
  taskPoolList.innerHTML = "";

  if (state.isLoading && state.orders.length === 0 && state.opshopPickups.length === 0) {
    const loadingState = document.createElement("p");
    loadingState.className = "empty-board";
    loadingState.textContent = "Loading Orders from backend...";
    taskPoolList.append(loadingState);
    return;
  }

  if (state.errorMessage && state.orders.length === 0 && state.opshopPickups.length === 0) {
    const errorState = document.createElement("p");
    errorState.className = "empty-board";
    errorState.textContent = "Board data is unavailable. Use Retry after the backend is running.";
    taskPoolList.append(errorState);
    return;
  }

  const unassignedOrders = getUnassignedOrders();
  const filteredOrders = getFilteredUnassignedOrders();

  taskPoolList.append(
    createOpShopPickupSection({
      onExportOpShopRunSheet,
      onOpenOncallOpShopPickupList,
      onOpenOpShopPickupList,
      oncallPickups: state.oncallOpShopPickups,
      pickups: state.scheduledOpShopPickups,
    }),
  );

  taskPoolList.append(
    createDeliveryOrderSection({
      filteredOrders,
      getPendingSelection,
      onAssignTask,
      onOpenOrderDetail,
      onPendingSelectionChange,
      unassignedOrders,
    }),
  );
}

function createTaskPoolSection({ className, titleText }) {
  const section = document.createElement("section");
  section.className = `task-pool-section ${className}`;

  const heading = document.createElement("div");
  heading.className = "task-pool-section-heading";

  const title = document.createElement("h3");
  title.textContent = titleText;

  heading.append(title);
  section.append(heading);
  return section;
}

function createOpShopPickupSection({
  onExportOpShopRunSheet,
  oncallPickups,
  onOpenOncallOpShopPickupList,
  pickups,
  onOpenOpShopPickupList,
}) {
  const section = createTaskPoolSection({
    className: "task-pool-section-opshop",
    titleText: "OP SHOP PICKUP",
  });

  const list = document.createElement("div");
  list.className = "task-pool-section-grid opshop-summary-grid";

  list.append(createOpShopPickupListSummaryCard(pickups, onOpenOpShopPickupList));
  list.append(createOncallOpShopPickupListSummaryCard(oncallPickups, onOpenOncallOpShopPickupList));

  const exportButton = document.createElement("button");
  exportButton.type = "button";
  exportButton.className = "button-secondary opshop-run-sheet-export-button";
  exportButton.disabled = state.isLoading || state.isSaving || state.isOpShopRunSheetExporting;
  exportButton.textContent = state.isOpShopRunSheetExporting
    ? "Exporting OP SHOP Run Sheet..."
    : "Export OP SHOP Run Sheet";
  exportButton.addEventListener("click", onExportOpShopRunSheet);

  section.append(list, exportButton);
  return section;
}

function createDeliveryOrderSection({
  filteredOrders,
  getPendingSelection,
  onAssignTask,
  onOpenOrderDetail,
  onPendingSelectionChange,
  unassignedOrders,
}) {
  const section = createTaskPoolSection({
    className: "task-pool-section-delivery",
    titleText: "DELIVERY ORDERS",
  });

  const list = document.createElement("div");
  list.className = "task-pool-section-grid";

  if (unassignedOrders.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = "No unassigned Delivery Orders.";
    list.append(emptyState);
    section.append(list);
    return section;
  }

  if (filteredOrders.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = "No matching unassigned orders.";
    list.append(emptyState);
    section.append(list);
    return section;
  }

  filteredOrders.forEach((order) => {
    list.append(createDeliveryOrderCard(order, {
      getPendingSelection,
      onAssignTask,
      onOpenOrderDetail,
      onPendingSelectionChange,
    }));
  });

  section.append(list);
  return section;
}

function createOpShopPickupListSummaryCard(pickups, onOpenOpShopPickupList) {
  const card = document.createElement("article");
  card.className = "order-card opshop-pickup-list-summary-card";

  const content = document.createElement("div");
  content.className = "opshop-pickup-list-summary-main";

  const kicker = document.createElement("p");
  kicker.className = "compact-invoice";
  kicker.textContent = "Scheduled Regular";

  const title = document.createElement("h3");
  title.className = "compact-suburb";
  title.textContent = "Regular OP SHOP Pickup List";

  const summary = document.createElement("p");
  summary.className = "compact-note opshop-pickup-note";
  summary.textContent =
    pickups.length === 0
      ? "No OP SHOP PICKUP tasks for this Regular pickup week."
      : `${pickups.length} scheduled pickups in this Regular pickup week.`;

  const meta = document.createElement("div");
  meta.className = "compact-meta opshop-pickup-meta";
  meta.append(
    createBadge(`Count: ${pickups.length}`, "good"),
    createBadge(`Window: ${getWindowLabel()}`),
    createBadge("ACTIVE / ASSIGNED"),
  );

  const openButton = document.createElement("button");
  openButton.type = "button";
  openButton.textContent = "Open List";
  openButton.addEventListener("click", onOpenOpShopPickupList);

  content.append(kicker, title, summary, meta, openButton);
  card.append(content);
  return card;
}

function createOncallOpShopPickupListSummaryCard(pickups, onOpenOncallOpShopPickupList) {
  const card = document.createElement("article");
  card.className = "order-card opshop-pickup-list-summary-card opshop-oncall-list-summary-card";

  const content = document.createElement("div");
  content.className = "opshop-pickup-list-summary-main";

  const kicker = document.createElement("p");
  kicker.className = "compact-invoice";
  kicker.textContent = "Oncall Requests";

  const title = document.createElement("h3");
  title.className = "compact-suburb";
  title.textContent = "Oncall OP SHOP Pickup List";

  const summary = document.createElement("p");
  summary.className = "compact-note opshop-pickup-note";
  summary.textContent =
    pickups.length === 0
      ? "No Oncall OP SHOP pickups added."
      : `${pickups.length} Oncall pickups added.`;

  const meta = document.createElement("div");
  meta.className = "compact-meta opshop-pickup-meta";
  meta.append(
    createBadge(`Count: ${pickups.length}`, "good"),
    createBadge("Created tasks only"),
    createBadge("ACTIVE / ASSIGNED"),
  );

  const openButton = document.createElement("button");
  openButton.type = "button";
  openButton.textContent = "Open List";
  openButton.addEventListener("click", onOpenOncallOpShopPickupList);

  content.append(kicker, title, summary, meta, openButton);
  card.append(content);
  return card;
}

function getWindowLabel() {
  const start = parseLocalDate(state.opshopRegularListWindowStart || state.dispatchDate);
  const end = parseLocalDate(state.opshopRegularListWindowEnd || state.dispatchDate);
  if (!start || !end) {
    return "Regular pickup week";
  }
  return `${formatDateShort(start)} to ${formatDateShort(end)}`;
}

function parseLocalDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) {
    return null;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function formatDateShort(date) {
  return `${date.getDate()}/${date.getMonth() + 1}`;
}

function createDeliveryOrderCard(order, {
  getPendingSelection,
  onAssignTask,
  onOpenOrderDetail,
  onPendingSelectionChange,
}) {
  const card = document.createElement("article");
  card.className = "order-card order-card-compact";
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `View details for ${order.invoice_number || order.order_id}`);
  card.addEventListener("click", () => onOpenOrderDetail(order.order_id));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenOrderDetail(order.order_id);
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
    createBadge(`Load: ${formatOrderLoadQuantity(order)}`),
    createBadge(getUrgencyLabel(order), isUrgent(order) ? "urgent" : "neutral"),
    createBadge(`Delivery Date: ${formatOptional(order.delivery_date)}`),
    createBadge(`Start: ${formatOptional(order.start_time)}`),
  );

  const note = document.createElement("p");
  note.className = "compact-note";
  note.textContent = `Note: ${truncateText(order.note || "None")}`;

  content.append(invoice, company, suburb, meta, note);

  const controls = createAssignmentControls({
    getPendingSelection,
    onAssignTask,
    onPendingSelectionChange,
    taskId: order.order_id,
    taskLabel: "Order",
    taskType: "ORDER",
  });

  card.append(content, controls);
  return card;
}

function createAssignmentControls({
  getPendingSelection,
  onAssignTask,
  onPendingSelectionChange,
  taskId,
  taskLabel,
  taskType,
}) {
  const selection = getPendingSelection(taskType, taskId);
  const controlIdSuffix = `${taskType.toLowerCase()}-${taskId}`;
  const controls = document.createElement("div");
  controls.className = "order-controls compact-order-controls";
  controls.addEventListener("click", (event) => event.stopPropagation());
  controls.addEventListener("keydown", (event) => event.stopPropagation());

  const driverLabel = document.createElement("label");
  driverLabel.textContent = "Driver";
  driverLabel.setAttribute("for", `driver-${controlIdSuffix}`);

  const driverSelect = document.createElement("select");
  driverSelect.id = `driver-${controlIdSuffix}`;
  driverSelect.disabled = state.isSaving || state.isLoading;
  driverSelect.append(createOption("", "Select driver", selection.driver_id === ""));
  state.drivers.forEach((driver) => {
    driverSelect.append(createOption(driver.driver_id, driver.name, selection.driver_id === driver.driver_id));
  });

  const tripLabel = document.createElement("label");
  tripLabel.textContent = "Trip";
  tripLabel.setAttribute("for", `trip-${controlIdSuffix}`);

  const tripSelect = document.createElement("select");
  tripSelect.id = `trip-${controlIdSuffix}`;
  tripSelect.disabled = state.isSaving || state.isLoading;
  tripSelect.append(createOption("trip1", "trip1", selection.trip_no !== "trip2"));
  tripSelect.append(createOption("trip2", "trip2", selection.trip_no === "trip2"));

  const assignButton = document.createElement("button");
  assignButton.type = "button";
  assignButton.disabled = !selection.driver_id || state.isSaving || state.isLoading;
  assignButton.textContent = state.isSaving ? "Saving..." : "Assign";
  assignButton.title = selection.driver_id
    ? `Assign this ${taskLabel} to the selected Driver and Trip`
    : "Select a driver to enable Assign";

  driverSelect.addEventListener("change", () => {
    onPendingSelectionChange(taskType, taskId, { driver_id: driverSelect.value });
    assignButton.disabled = driverSelect.value === "" || state.isSaving || state.isLoading;
    assignButton.title = driverSelect.value
      ? `Assign this ${taskLabel} to the selected Driver and Trip`
      : "Select a driver to enable Assign";
  });

  tripSelect.addEventListener("change", () => {
    onPendingSelectionChange(taskType, taskId, { trip_no: tripSelect.value || "trip1" });
  });

  assignButton.addEventListener("click", (event) => {
    event.stopPropagation();
    onAssignTask(taskType, taskId);
  });

  controls.append(driverLabel, driverSelect, tripLabel, tripSelect, assignButton);
  return controls;
}
