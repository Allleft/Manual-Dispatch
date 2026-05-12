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
  getDisplayPalletQuantity,
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
  onOpenOrderDetail,
  onPendingSelectionChange,
  onAssign,
}) {
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
      createBadge(`Pallet: ${getDisplayPalletQuantity(order)}`),
      createBadge(getUrgencyLabel(order), isUrgent(order) ? "urgent" : "neutral"),
      createBadge(`Delivery Date: ${formatOptional(order.delivery_date)}`),
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
      onPendingSelectionChange(order.order_id, { driver_id: driverSelect.value });
      assignButton.disabled = driverSelect.value === "" || state.isSaving || state.isLoading;
      assignButton.title = driverSelect.value
        ? "Assign this Order to the selected Driver and Trip"
        : "Select a driver to enable Assign";
    });

    tripSelect.addEventListener("change", () => {
      onPendingSelectionChange(order.order_id, { trip_no: tripSelect.value || "trip1" });
    });

    assignButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onAssign(order.order_id);
    });

    controls.append(driverLabel, driverSelect, tripLabel, tripSelect, assignButton);
    card.append(content, controls);
    taskPoolList.append(card);
  });
}
