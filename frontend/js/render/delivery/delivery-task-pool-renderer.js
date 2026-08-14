import { createIcon } from "../../utils/icon-utils.js";

import {
  formatOptional,
  formatProductDetailLine,
} from "../../utils/format-utils.js";

import {
  isDeliveryOrderUrgent,
  normalizeDeliveryOrderUrgency,
  sortDeliveryTaskPoolOrders,
} from "../../utils/delivery-order-priority-utils.js";

import {
  assignmentMap,
  createSelect,
  createTextInput,
  createActionButton,
  createBadge,
  createChip,
  createEmptyState,
  formatLoad,
  isBusy,
} from "./delivery-renderer-utils.js";

export function createDeliveryTaskPool(board, state, actions) {
  if (!board) {
    return createEmptyState("No Delivery workspace data loaded.", "document");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-delivery-task-pool";
  const assignments = assignmentMap(board);
  const unassignedOrders = (board.orders || []).filter(
    (order) => !assignments.has(order.order_id),
  );
  const filteredOrders = sortDeliveryTaskPoolOrders(
    filterDeliveryTaskPoolOrders(unassignedOrders, state.deliveryTaskPoolFilters),
  );

  wrapper.append(createDeliveryTaskPoolPanel(unassignedOrders, filteredOrders, state, actions));
  wrapper.append(createDeliveryTaskPoolOrderGrid(
    unassignedOrders,
    filteredOrders,
    board,
    state,
    actions,
  ));
  return wrapper;
}

export function updateDeliveryTaskPoolFilteredContent(board, state, actions, root = document) {
  const wrapper = root.querySelector(".workspace-delivery-task-pool");
  const currentGrid = wrapper?.querySelector(".workspace-order-grid");
  if (!board || !wrapper || !currentGrid) {
    return false;
  }
  const assignments = assignmentMap(board);
  const unassignedOrders = (board.orders || []).filter(
    (order) => !assignments.has(order.order_id),
  );
  const filteredOrders = sortDeliveryTaskPoolOrders(
    filterDeliveryTaskPoolOrders(unassignedOrders, state.deliveryTaskPoolFilters),
  );
  const count = wrapper.querySelector(".workspace-filter-count");
  if (count) {
    count.textContent = `${filteredOrders.length} of ${unassignedOrders.length} visible Orders`;
  }
  currentGrid.replaceWith(createDeliveryTaskPoolOrderGrid(
    unassignedOrders,
    filteredOrders,
    board,
    state,
    actions,
  ));
  return true;
}

function createDeliveryTaskPoolOrderGrid(unassignedOrders, filteredOrders, board, state, actions) {
  const orderGrid = document.createElement("div");
  orderGrid.className = "workspace-card-grid workspace-order-grid";
  if (!unassignedOrders.length) {
    orderGrid.append(createEmptyState("No unassigned Delivery Orders are available.", "document"));
  } else if (!filteredOrders.length) {
    orderGrid.append(createEmptyState("No unassigned Delivery Orders match the filters.", "document"));
  } else {
    filteredOrders.forEach((order) => {
      orderGrid.append(createOrderCard(order, board, state, actions));
    });
  }
  return orderGrid;
}

export function createDeliveryTaskPoolPanel(unassignedOrders, filteredOrders, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-context-panel workspace-context-panel-delivery workspace-task-pool-panel";
  const header = document.createElement("div");
  header.className = "workspace-task-pool-panel-header";
  const titleGroup = document.createElement("div");
  titleGroup.className = "workspace-task-pool-title";
  const icon = document.createElement("span");
  icon.className = "workspace-task-pool-title-icon";
  icon.append(createIcon("truck"));
  const copy = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = "Delivery Orders";
  copy.append(title);
  titleGroup.append(icon, copy);

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-task-pool-actions";
  actionsRow.append(
    createActionButton("Add Order", actions.openAddDeliveryOrder, {
      primary: true,
      disabled: state.isDeliveryWorkspaceLoading,
      iconName: "plus",
    }),
    createActionButton("Import Delivery Document", actions.openDeliveryAttacheImport, {
      disabled: state.isDeliveryWorkspaceLoading,
      primary: true,
      iconName: "cloud-upload",
    }),
    createActionButton("Driver & Vehicle Specification", actions.openDeliverySpecifications, {
      disabled: state.isDeliveryWorkspaceLoading,
      iconName: "truck",
    }),
  );
  header.append(titleGroup, actionsRow);

  const filtersRow = document.createElement("div");
  filtersRow.className = "workspace-delivery-filter-bar";
  const filters = state.deliveryTaskPoolFilters || {};
  const search = createTextInput(
    "Search Orders",
    filters.search || "",
    "Invoice, invoice date, order #, company, phone, address, suburb, postcode, product, notes",
    (value) => actions.updateDeliveryTaskPoolFilter("search", value),
  );
  const date = createTextInput(
    "Delivery Date",
    filters.delivery_date || "",
    "",
    (value) => actions.updateDeliveryTaskPoolFilter("delivery_date", value),
    { type: "date" },
  );
  const urgency = createSelect(
    "Urgency",
    filters.urgency || "All",
    ["All", "Normal", "Urgent"].map((item) => ({ value: item, label: item })),
    (value) => actions.updateDeliveryTaskPoolFilter("urgency", value),
  );
  const clear = createActionButton("Clear filters", actions.clearDeliveryTaskPoolFilters, {
    disabled: !hasDeliveryTaskPoolFilters(filters),
  });
  const allDates = createActionButton("All delivery dates", () => actions.updateDeliveryTaskPoolFilter("delivery_date", ""), {
    disabled: !filters.delivery_date,
  });
  const count = document.createElement("span");
  count.className = "workspace-filter-count";
  count.textContent = `${filteredOrders.length} of ${unassignedOrders.length} visible Orders`;
  filtersRow.append(search, urgency, date, allDates, clear, count);
  panel.append(header, filtersRow);
  return panel;
}

export function createOrderCard(order, board, state, actions) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-order-card";
  const urgency = normalizeDeliveryOrderUrgency(order.urgency);
  const isUrgent = isDeliveryOrderUrgent(urgency);
  card.classList.toggle("workspace-order-card-urgent", isUrgent);
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `View Delivery Order ${formatOptional(order.invoice_number, order.order_id)}`);
  card.addEventListener("click", () => actions.openDeliveryOrderDetail(order.order_id));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      actions.openDeliveryOrderDetail(order.order_id);
    }
  });
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const eyebrow = document.createElement("span");
  eyebrow.className = "workspace-record-kicker";
  eyebrow.textContent = `Invoice # ${formatOptional(order.invoice_number, order.order_id)}`;
  const orderNumber = document.createElement("span");
  orderNumber.className = "workspace-order-number";
  orderNumber.textContent = `Order # ${formatOptional(order.order_no)}`;
  const title = document.createElement("h3");
  title.textContent = formatOptional(order.company_name);
  const suburb = document.createElement("p");
  suburb.className = "workspace-order-suburb";
  suburb.textContent = formatOptional(order.suburb);
  identity.append(eyebrow, orderNumber, title, suburb);
  const urgencyBadge = createBadge(urgency);
  urgencyBadge.classList.toggle("workspace-order-badge-urgent", isUrgent);
  top.append(identity, urgencyBadge);

  const chips = document.createElement("div");
  chips.className = "workspace-order-chip-row";
  const urgencyChip = createChip(urgency);
  urgencyChip.classList.toggle("workspace-order-chip-urgent", isUrgent);
  chips.append(
    createChip(`Load: ${formatLoad(order)}`),
    urgencyChip,
    createChip(`Invoice Date: ${formatOptional(order.invoice_date)}`),
    createChip(`Delivery Date: ${formatOptional(order.delivery_date)}`),
    createChip(`Start: ${formatOptional(order.start_time, "-")}`),
  );
  const body = document.createElement("div");
  body.className = "workspace-order-card-body";
  const info = document.createElement("div");
  info.className = "workspace-order-card-info";
  info.append(top, chips);
  const products = document.createElement("p");
  products.className = "workspace-order-products-preview";
  products.textContent = "Products: " + ((order.product_lines || [])
    .map((line, index) => formatProductDetailLine(line, index + 1))
    .join("; ") || "No product lines");
  info.append(products);
  if (order.note) {
    const note = document.createElement("p");
    note.className = "workspace-order-note-preview";
    note.textContent = `Note: ${String(order.note).slice(0, 110)}${String(order.note).length > 110 ? "..." : ""}`;
    info.append(note);
  }
  body.append(info, createOrderAssignmentControls(order, board, state, actions));
  card.append(body);
  return card;
}

export function createOrderAssignmentControls(order, board, state, actions) {
  const controls = document.createElement("div");
  controls.className = "workspace-order-assignment-controls";
  controls.addEventListener("click", (event) => event.stopPropagation());
  controls.addEventListener("keydown", (event) => event.stopPropagation());
  const draft = state.deliveryAssignmentDrafts?.[order.order_id] || {};
  const selectedTripNo = draft.trip_no || "trip1";
  const driverSelect = createSelect(
    "Driver",
    draft.driver_id || "",
    [{ value: "", label: "Select driver" }].concat(
      (board.drivers || []).map((driver) => ({
        value: driver.driver_id,
        label: formatOptional(driver.name, driver.driver_id),
      })),
    ),
    (value) => actions.updateDeliveryAssignmentDraft(order.order_id, "driver_id", value),
  );
  const tripSelect = createSelect(
    "Trip",
    selectedTripNo,
    [
      { value: "", label: "Select trip" },
      { value: "trip1", label: "Trip 1" },
      { value: "trip2", label: "Trip 2" },
    ],
    (value) => actions.updateDeliveryAssignmentDraft(order.order_id, "trip_no", value),
  );
  const assignButton = createActionButton(
    "Assign",
    () => actions.applyDeliveryOrderAssignment(order.order_id),
    {
      disabled: !draft.driver_id || !selectedTripNo || isBusy(state, `delivery-assignment:${order.order_id}`),
      primary: true,
      iconName: "plus",
    },
  );
  controls.append(driverSelect, tripSelect, assignButton);
  return controls;
}

export function filterDeliveryTaskPoolOrders(orders, filters = {}) {
  const search = normalizeSearch(filters.search || "");
  const deliveryDate = filters.delivery_date || "";
  const urgency = String(filters.urgency || "All").trim();
  return (orders || []).filter((order) => {
    if (deliveryDate && order.delivery_date !== deliveryDate) {
      return false;
    }
    if (
      urgency.toLowerCase() !== "all"
      && normalizeDeliveryOrderUrgency(order.urgency) !== normalizeDeliveryOrderUrgency(urgency)
    ) {
      return false;
    }
    if (!search) {
      return true;
    }
    return deliveryOrderSearchText(order).includes(search);
  });
}

export function deliveryOrderSearchText(order) {
  return normalizeSearch([
    order.invoice_number,
    order.invoice_date,
    order.order_no,
    order.company_name,
    order.phone,
    order.delivery_address,
    order.suburb,
    order.postcode,
    order.note,
    ...(order.product_lines || []).flatMap((line) => [
      line.product_code,
      line.product_name,
    ]),
  ].filter(Boolean).join(" "));
}

export function normalizeSearch(value) {
  return String(value || "").trim().toLowerCase();
}

export function hasDeliveryTaskPoolFilters(filters = {}) {
  return Boolean(
    (filters.search || "").trim()
    || filters.delivery_date
    || (filters.urgency && filters.urgency !== "All")
  );
}
