import { createIcon } from "../utils/icon-utils.js";
import {
  formatOptional,
  formatPluralLoadUnit,
} from "../utils/format-utils.js";


const DELIVERY_TABS = [
  { route: "delivery/task-pool", label: "Task Pool" },
  { route: "delivery/run-sheet", label: "Run Sheets" },
  { route: "delivery/history", label: "Saved History" },
];


export function renderDeliveryWorkspace(root, { state, onDispatchDateChange }) {
  root.innerHTML = "";
  const page = createWorkspacePage(state, onDispatchDateChange);
  const content = document.createElement("div");
  content.className = "workspace-content";

  if (state.isDeliveryWorkspaceLoading) {
    content.append(createStatus("Loading Order Delivery workspace...", "loading"));
  } else if (state.deliveryWorkspaceError) {
    content.append(createStatus(state.deliveryWorkspaceError, "error"));
  } else if (state.workspaceRoute === "delivery/task-pool") {
    content.append(createDeliveryTaskPool(state.deliveryBoard));
  } else {
    const savedOnly = state.workspaceRoute === "delivery/history";
    content.append(createRunSheetList(state.deliveryRunSheets, savedOnly));
  }

  page.append(content);
  root.append(page);
}


function createWorkspacePage(state, onDispatchDateChange) {
  const page = document.createElement("section");
  page.className = "workspace-page workspace-page-delivery";

  const heading = document.createElement("header");
  heading.className = "workspace-page-heading";
  const titleGroup = document.createElement("div");
  titleGroup.className = "workspace-page-title-group";
  const icon = document.createElement("span");
  icon.className = "workspace-page-icon";
  icon.append(createIcon("truck"));
  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Delivery workspace";
  const title = document.createElement("h2");
  title.textContent = "Order Delivery";
  const description = document.createElement("p");
  description.textContent = "Review active orders and independent Delivery Run Sheet records.";
  copy.append(kicker, title, description);
  titleGroup.append(icon, copy);
  heading.append(titleGroup, createDateControl(state, onDispatchDateChange));

  const nav = document.createElement("nav");
  nav.className = "workspace-tabs workspace-tabs-delivery";
  nav.setAttribute("aria-label", "Order Delivery workspace");
  DELIVERY_TABS.forEach((tab) => nav.append(createTab(tab, state.workspaceRoute)));

  const notice = createStatus(
    "Workspace actions will be enabled in the next implementation stage.",
    "notice",
  );
  page.append(heading, nav, notice);
  return page;
}


function createDateControl(state, onDispatchDateChange) {
  const label = document.createElement("label");
  label.className = "workspace-date-control";
  label.textContent = "Dispatch date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = state.dispatchDate;
  input.disabled = state.isDeliveryWorkspaceLoading;
  input.addEventListener("change", () => onDispatchDateChange(input.value));
  label.append(input);
  return label;
}


function createTab(tab, activeRoute) {
  const link = document.createElement("a");
  link.href = `#${tab.route}`;
  link.className = "workspace-tab";
  link.textContent = tab.label;
  if (tab.route === activeRoute) {
    link.classList.add("workspace-tab-active");
    link.setAttribute("aria-current", "page");
  }
  return link;
}


function createDeliveryTaskPool(board) {
  if (!board) {
    return createEmptyState("No Delivery workspace data loaded.", "document");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const assignments = new Map(
    (board.assignments || []).map((assignment) => [assignment.task_id, assignment]),
  );
  const drivers = new Map((board.drivers || []).map((driver) => [driver.driver_id, driver]));
  const assignedCount = (board.orders || []).filter((order) => assignments.has(order.order_id)).length;
  const totalPallets = (board.orders || []).reduce(
    (total, order) => total + Number(order.pallet_quantity || 0),
    0,
  );
  const totalBags = (board.orders || []).reduce(
    (total, order) => total + Number(order.loose_bags_quantity || 0),
    0,
  );

  wrapper.append(
    createMetricGrid([
      ["Active orders", (board.orders || []).length, "document"],
      ["Assigned", assignedCount, "user"],
      ["Pallets", totalPallets, "box"],
      ["Loose bags", totalBags, "bag"],
    ]),
  );

  const ordersSection = createSectionHeading(
    "Active Delivery Orders",
    `${(board.orders || []).length} orders in this dispatch workspace`,
  );
  const orderGrid = document.createElement("div");
  orderGrid.className = "workspace-card-grid workspace-order-grid";
  if (!(board.orders || []).length) {
    orderGrid.append(createEmptyState("No active Delivery Orders are available.", "document"));
  } else {
    board.orders.forEach((order) => {
      orderGrid.append(createOrderCard(order, assignments.get(order.order_id), drivers));
    });
  }
  wrapper.append(ordersSection, orderGrid);

  wrapper.append(createDeliveryContext(board, drivers));
  return wrapper;
}


function createOrderCard(order, assignment, drivers) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-order-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const eyebrow = document.createElement("span");
  eyebrow.className = "workspace-record-kicker";
  eyebrow.textContent = formatOptional(order.invoice_number, order.order_id);
  const title = document.createElement("h3");
  title.textContent = formatOptional(order.company_name);
  const address = document.createElement("p");
  address.textContent = [order.delivery_address, order.suburb, order.postcode]
    .filter(Boolean)
    .join(", ");
  identity.append(eyebrow, title, address);
  top.append(identity, createBadge(formatOptional(order.urgency, "Normal")));

  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Delivery date", order.delivery_date);
  appendFact(
    facts,
    "Assigned driver",
    assignment ? formatOptional(drivers.get(assignment.driver_id)?.name, assignment.driver_id) : "Unassigned",
  );
  appendFact(facts, "Delivery trip", assignment ? assignment.trip_no : "Not assigned");
  appendFact(facts, "Load", formatLoad(order));

  const products = document.createElement("div");
  products.className = "workspace-product-lines";
  const productTitle = document.createElement("strong");
  productTitle.textContent = "Products";
  const list = document.createElement("ul");
  (order.product_lines || []).forEach((line) => {
    const item = document.createElement("li");
    item.textContent = `${formatOptional(line.product_name)} · ${line.quantity} ${formatPluralLoadUnit(line.unit, line.quantity)}`;
    list.append(item);
  });
  if (!list.children.length) {
    const item = document.createElement("li");
    item.textContent = "No product lines recorded";
    list.append(item);
  }
  products.append(productTitle, list);
  card.append(top, facts, products);
  return card;
}


function createDeliveryContext(board, drivers) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-delivery";
  section.append(
    createSectionHeading(
      "Driver and Vehicle Context",
      "Current selections and saved Delivery Run Sheet locks",
    ),
  );
  const list = document.createElement("div");
  list.className = "workspace-context-list";
  const vehicleMap = new Map((board.vehicles || []).map((vehicle) => [vehicle.vehicle_id, vehicle]));
  (board.driver_vehicle_assignments || []).forEach((assignment) => {
    list.append(
      createContextRow(
        formatOptional(drivers.get(assignment.driver_id)?.name, assignment.driver_id),
        `${assignment.delivery_date} · ${formatOptional(vehicleMap.get(assignment.vehicle_id)?.rego, assignment.vehicle_id)}`,
      ),
    );
  });
  (board.saved_vehicle_assignment_locks || []).forEach((lock) => {
    list.append(
      createContextRow(
        `${formatOptional(drivers.get(lock.driver_id)?.name, lock.driver_id)} · Saved`,
        `${lock.delivery_date} · vehicle selection locked`,
      ),
    );
  });
  if (!list.children.length) {
    list.append(createEmptyState("No vehicle selections or saved locks for this dispatch date.", "truck"));
  }
  section.append(list);
  return section;
}


function createRunSheetList(runSheets, savedOnly) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const filtered = (runSheets || []).filter(
    (runSheet) => !savedOnly || runSheet.status === "SAVED",
  );
  wrapper.append(
    createSectionHeading(
      savedOnly ? "Saved Delivery Run Sheet History" : "Delivery Run Sheets",
      `${filtered.length} ${savedOnly ? "saved records" : "generated and saved records"}`,
    ),
  );
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-run-sheet-grid";
  if (!filtered.length) {
    grid.append(
      createEmptyState(
        savedOnly ? "No saved Delivery Run Sheets for this dispatch date." : "No Delivery Run Sheets for this dispatch date.",
        "history",
      ),
    );
  } else {
    filtered.forEach((runSheet) => grid.append(createRunSheetCard(runSheet)));
  }
  wrapper.append(grid);
  return wrapper;
}


function createRunSheetCard(runSheet) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-run-sheet-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const title = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.className = "workspace-record-kicker";
  kicker.textContent = runSheet.delivery_date;
  const heading = document.createElement("h3");
  heading.textContent = formatOptional(runSheet.driver_name_snapshot, runSheet.driver_id);
  title.append(kicker, heading);
  top.append(title, createBadge(runSheet.status, runSheet.status.toLowerCase()));

  const tripCounts = new Map(
    (runSheet.trips || []).map((trip) => [trip.trip_no, (trip.orders || []).length]),
  );
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Vehicle", formatOptional(runSheet.vehicle_rego_snapshot, "Not selected"));
  appendFact(facts, "Trip 1 orders", tripCounts.get("trip1") || 0);
  appendFact(facts, "Trip 2 orders", tripCounts.get("trip2") || 0);
  appendFact(facts, "Total pallets", runSheet.total_pallets || 0);
  appendFact(facts, "Total bags", runSheet.total_loose_bags || 0);
  appendFact(
    facts,
    runSheet.status === "SAVED" ? "Saved" : "Generated",
    runSheet.saved_at || runSheet.generated_at,
  );
  card.append(top, facts);
  return card;
}


function createMetricGrid(metrics) {
  const grid = document.createElement("div");
  grid.className = "workspace-metric-grid workspace-metric-grid-delivery";
  metrics.forEach(([label, value, iconName]) => {
    const card = document.createElement("div");
    card.className = "workspace-metric-card";
    card.append(createIcon(iconName));
    const copy = document.createElement("div");
    const number = document.createElement("strong");
    number.textContent = String(value);
    const text = document.createElement("span");
    text.textContent = label;
    copy.append(number, text);
    card.append(copy);
    grid.append(card);
  });
  return grid;
}


function createSectionHeading(titleText, descriptionText) {
  const heading = document.createElement("div");
  heading.className = "workspace-section-heading";
  const title = document.createElement("h3");
  title.textContent = titleText;
  const description = document.createElement("p");
  description.textContent = descriptionText;
  heading.append(title, description);
  return heading;
}


function createContextRow(titleText, detailText) {
  const row = document.createElement("div");
  row.className = "workspace-context-row";
  const title = document.createElement("strong");
  title.textContent = titleText;
  const detail = document.createElement("span");
  detail.textContent = detailText;
  row.append(title, detail);
  return row;
}


function appendFact(list, labelText, value) {
  const item = document.createElement("div");
  const label = document.createElement("dt");
  label.textContent = labelText;
  const detail = document.createElement("dd");
  detail.textContent = formatOptional(value);
  item.append(label, detail);
  list.append(item);
}


function createBadge(label, modifier = "") {
  const badge = document.createElement("span");
  badge.className = `workspace-badge${modifier ? ` workspace-badge-${modifier}` : ""}`;
  badge.textContent = label;
  return badge;
}


function createStatus(message, type) {
  const status = document.createElement("p");
  status.className = `workspace-status workspace-status-${type}`;
  status.setAttribute(type === "error" ? "role" : "aria-live", type === "error" ? "alert" : "polite");
  status.textContent = message;
  return status;
}


function createEmptyState(message, iconName) {
  const empty = document.createElement("div");
  empty.className = "workspace-empty-state";
  empty.append(createIcon(iconName));
  const text = document.createElement("p");
  text.textContent = message;
  empty.append(text);
  return empty;
}


function formatLoad(order) {
  const pallets = Number(order.pallet_quantity || 0);
  const bags = Number(order.loose_bags_quantity || 0);
  return `${pallets} ${formatPluralLoadUnit("PALLETS", pallets)} · ${bags} ${formatPluralLoadUnit("BAGS", bags)}`;
}
