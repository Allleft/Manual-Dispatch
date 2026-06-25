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


export function renderDeliveryWorkspace(
  root,
  { state, actions, onDispatchDateChange },
) {
  root.innerHTML = "";
  const page = createWorkspacePage(state, onDispatchDateChange);
  const content = document.createElement("div");
  content.className = "workspace-content";

  if (state.isDeliveryWorkspaceLoading) {
    content.append(createStatus("Loading Order Delivery workspace...", "loading"));
  } else if (state.deliveryWorkspaceError) {
    content.append(createStatus(state.deliveryWorkspaceError, "error"));
  } else {
    if (state.deliveryActionError) {
      content.append(createStatus(state.deliveryActionError, "error"));
    }
    if (state.workspaceRoute === "delivery/task-pool") {
      content.append(createDeliveryTaskPool(state.deliveryBoard, state, actions));
    } else {
      const savedOnly = state.workspaceRoute === "delivery/history";
      content.append(
        createRunSheetList(
          state.deliveryBoard,
          state.deliveryRunSheets,
          savedOnly,
          state,
          actions,
        ),
      );
    }
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
  description.textContent = "Assign orders and manage independent Delivery Run Sheet records.";
  copy.append(kicker, title, description);
  titleGroup.append(icon, copy);
  heading.append(titleGroup, createDateControl(state, onDispatchDateChange));

  const nav = document.createElement("nav");
  nav.className = "workspace-tabs workspace-tabs-delivery";
  nav.setAttribute("aria-label", "Order Delivery workspace");
  DELIVERY_TABS.forEach((tab) => nav.append(createTab(tab, state.workspaceRoute)));

  page.append(heading, nav);
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


function createDeliveryTaskPool(board, state, actions) {
  if (!board) {
    return createEmptyState("No Delivery workspace data loaded.", "document");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const assignments = assignmentMap(board);
  const drivers = driverMap(board);
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
      orderGrid.append(
        createOrderCard(order, assignments.get(order.order_id), drivers, state, actions),
      );
    });
  }
  wrapper.append(ordersSection, orderGrid);

  wrapper.append(createDeliveryContext(board, drivers, state, actions));
  return wrapper;
}


function createOrderCard(order, assignment, drivers, state, actions) {
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

  const controls = createOrderAssignmentControls(order, assignment, state, actions);
  const products = document.createElement("div");
  products.className = "workspace-product-lines";
  const productTitle = document.createElement("strong");
  productTitle.textContent = "Products";
  const list = document.createElement("ul");
  (order.product_lines || []).forEach((line) => {
    const item = document.createElement("li");
    item.textContent = `${formatOptional(line.product_name)} - ${line.quantity} ${formatPluralLoadUnit(line.unit, line.quantity)}`;
    list.append(item);
  });
  if (!list.children.length) {
    const item = document.createElement("li");
    item.textContent = "No product lines recorded";
    list.append(item);
  }
  products.append(productTitle, list);
  card.append(top, facts, controls, products);
  return card;
}


function createOrderAssignmentControls(order, assignment, state, actions) {
  const controls = document.createElement("div");
  controls.className = "workspace-action-row workspace-action-row-stacked";
  const draft = getOrderDraft(order.order_id, assignment, state);
  const driverSelect = createSelect(
    "Driver",
    draft.driver_id,
    [{ value: "", label: "Select driver" }].concat(
      (state.deliveryBoard?.drivers || []).map((driver) => ({
        value: driver.driver_id,
        label: driver.name,
      })),
    ),
    (value) => actions.updateDeliveryAssignmentDraft(order.order_id, "driver_id", value),
  );
  const tripSelect = createSelect(
    "Trip",
    draft.trip_no || "trip1",
    [
      { value: "trip1", label: "trip1" },
      { value: "trip2", label: "trip2" },
    ],
    (value) => actions.updateDeliveryAssignmentDraft(order.order_id, "trip_no", value),
  );
  const assignButton = createActionButton(
    assignment ? "Update" : "Assign",
    () => actions.applyDeliveryOrderAssignment(order.order_id),
    {
      disabled: !draft.driver_id || isBusy(state, `delivery-assignment:${order.order_id}`),
      primary: true,
    },
  );
  controls.append(driverSelect, tripSelect, assignButton);
  if (assignment) {
    controls.append(
      createActionButton(
        "Unassign",
        () => actions.unassignDeliveryOrder(order.order_id),
        {
          disabled: isBusy(state, `delivery-unassign:${order.order_id}`),
        },
      ),
    );
  }
  return controls;
}


function createDeliveryContext(board, drivers, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-delivery";
  section.append(
    createSectionHeading(
      "Driver and Vehicle Context",
      "Vehicle selections grouped by driver and delivery date",
    ),
  );
  const list = document.createElement("div");
  list.className = "workspace-context-list";
  const contexts = deliveryVehicleContexts(board);
  if (!contexts.length) {
    list.append(createEmptyState("No assigned orders need vehicle selection yet.", "truck"));
  } else {
    contexts.forEach((context) =>
      list.append(createVehicleControlRow(context, board, drivers, state, actions)),
    );
  }
  section.append(list);
  return section;
}


function createVehicleControlRow(context, board, drivers, state, actions) {
  const row = document.createElement("div");
  row.className = "workspace-context-row workspace-context-row-actions";
  const title = document.createElement("strong");
  title.textContent = `${formatOptional(drivers.get(context.driver_id)?.name, context.driver_id)} - ${context.delivery_date}`;
  const lock = findVehicleLock(board, context.delivery_date, context.driver_id);
  const currentAssignment = findVehicleAssignment(board, context.delivery_date, context.driver_id);
  const draftKey = `${context.delivery_date}|${context.driver_id}`;
  const selectedVehicleId =
    state.deliveryVehicleDrafts[draftKey] ?? currentAssignment?.vehicle_id ?? "";
  const vehicleSelect = createSelect(
    "Vehicle",
    selectedVehicleId,
    [{ value: "", label: "Select vehicle" }].concat(
      (board.vehicles || []).map((vehicle) => ({
        value: vehicle.vehicle_id,
        label: vehicle.rego,
      })),
    ),
    (value) => actions.updateDeliveryVehicleDraft(
      context.delivery_date,
      context.driver_id,
      value,
    ),
  );
  const isLocked = Boolean(lock);
  vehicleSelect.querySelector("select").disabled = isLocked;
  const applyButton = createActionButton(
    "Save vehicle",
    () => actions.applyDeliveryVehicleAssignment(context.delivery_date, context.driver_id),
    {
      disabled: isLocked || !selectedVehicleId || isBusy(state, `delivery-vehicle:${context.delivery_date}:${context.driver_id}`),
    },
  );
  const clearButton = createActionButton(
    "Clear",
    () => actions.clearDeliveryVehicleAssignment(context.delivery_date, context.driver_id),
    {
      disabled: isLocked || !currentAssignment || isBusy(state, `delivery-vehicle-clear:${context.delivery_date}:${context.driver_id}`),
    },
  );
  const message = document.createElement("span");
  message.textContent = isLocked
    ? "Saved Delivery Run Sheet locks this vehicle selection."
    : `${context.order_count} assigned orders`;
  row.append(title, message, vehicleSelect, applyButton, clearButton);
  return row;
}


function createRunSheetList(board, runSheets, savedOnly, state, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const filtered = (runSheets || []).filter(
    (runSheet) => !savedOnly || runSheet.status === "SAVED",
  );
  if (!savedOnly && board) {
    wrapper.append(createReadyRunSheetSection(board, runSheets, state, actions));
  }
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
    filtered.forEach((runSheet) => grid.append(createRunSheetCard(runSheet, state, actions)));
  }
  wrapper.append(grid);
  return wrapper;
}


function createReadyRunSheetSection(board, runSheets, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-delivery";
  section.append(
    createSectionHeading(
      "Ready to Generate",
      "Assigned order groups without a generated or saved Delivery Run Sheet",
    ),
  );
  const candidates = readyDeliveryRunSheetCandidates(board, runSheets);
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-run-sheet-grid";
  if (!candidates.length) {
    grid.append(createEmptyState("No Delivery Run Sheet candidates are ready.", "document"));
  } else {
    candidates.forEach((candidate) => {
      const card = document.createElement("article");
      card.className = "workspace-record-card workspace-run-sheet-card";
      const driver = (board.drivers || []).find((item) => item.driver_id === candidate.driver_id);
      const heading = document.createElement("h3");
      heading.textContent = formatOptional(driver?.name, candidate.driver_id);
      const facts = document.createElement("dl");
      facts.className = "workspace-fact-grid";
      appendFact(facts, "Delivery date", candidate.delivery_date);
      appendFact(facts, "Orders", candidate.orders.length);
      appendFact(facts, "Total pallets", candidate.total_pallets);
      appendFact(facts, "Total bags", candidate.total_loose_bags);
      const button = createActionButton(
        "Generate",
        () => actions.generateDeliveryRunSheet(candidate),
        {
          disabled: isBusy(state, `delivery-generate:${candidate.delivery_date}:${candidate.driver_id}`),
          primary: true,
        },
      );
      card.append(heading, facts, button);
      grid.append(card);
    });
  }
  section.append(grid);
  return section;
}


function createRunSheetCard(runSheet, state, actions) {
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
  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  if (runSheet.status === "GENERATED") {
    actionsRow.append(
      createActionButton("Save", () => actions.saveDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-save:${runSheet.run_sheet_id}`),
        primary: true,
      }),
      createActionButton("Cancel", () => actions.cancelDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-cancel:${runSheet.run_sheet_id}`),
      }),
    );
  }
  if (runSheet.status === "SAVED") {
    actionsRow.append(
      createActionButton("Export", () => actions.exportDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-export:${runSheet.run_sheet_id}`),
        primary: true,
      }),
    );
  }
  card.append(top, facts, actionsRow);
  return card;
}


function readyDeliveryRunSheetCandidates(board, runSheets) {
  const reservedKeys = new Set(
    (runSheets || [])
      .filter((runSheet) => ["GENERATED", "SAVED"].includes(runSheet.status))
      .map((runSheet) => `${runSheet.delivery_date}|${runSheet.driver_id}`),
  );
  const orders = new Map((board.orders || []).map((order) => [order.order_id, order]));
  const groups = new Map();
  (board.assignments || []).forEach((assignment) => {
    const order = orders.get(assignment.task_id);
    if (!order?.delivery_date) {
      return;
    }
    const key = `${order.delivery_date}|${assignment.driver_id}`;
    if (reservedKeys.has(key)) {
      return;
    }
    if (!groups.has(key)) {
      groups.set(key, {
        delivery_date: order.delivery_date,
        driver_id: assignment.driver_id,
        orders: [],
        total_pallets: 0,
        total_loose_bags: 0,
      });
    }
    const group = groups.get(key);
    group.orders.push(order);
    group.total_pallets += Number(order.pallet_quantity || 0);
    group.total_loose_bags += Number(order.loose_bags_quantity || 0);
  });
  return Array.from(groups.values()).sort((left, right) =>
    `${left.delivery_date}|${left.driver_id}`.localeCompare(`${right.delivery_date}|${right.driver_id}`),
  );
}


function deliveryVehicleContexts(board) {
  const orders = new Map((board.orders || []).map((order) => [order.order_id, order]));
  const groups = new Map();
  (board.assignments || []).forEach((assignment) => {
    const order = orders.get(assignment.task_id);
    if (!order?.delivery_date) {
      return;
    }
    const key = `${order.delivery_date}|${assignment.driver_id}`;
    if (!groups.has(key)) {
      groups.set(key, {
        delivery_date: order.delivery_date,
        driver_id: assignment.driver_id,
        order_count: 0,
      });
    }
    groups.get(key).order_count += 1;
  });
  return Array.from(groups.values()).sort((left, right) =>
    `${left.delivery_date}|${left.driver_id}`.localeCompare(`${right.delivery_date}|${right.driver_id}`),
  );
}


function findVehicleAssignment(board, deliveryDate, driverId) {
  return (board.driver_vehicle_assignments || []).find(
    (assignment) =>
      assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
  );
}


function findVehicleLock(board, deliveryDate, driverId) {
  return (board.saved_vehicle_assignment_locks || []).find(
    (lock) => lock.delivery_date === deliveryDate && lock.driver_id === driverId,
  );
}


function assignmentMap(board) {
  return new Map(
    (board.assignments || []).map((assignment) => [assignment.task_id, assignment]),
  );
}


function driverMap(board) {
  return new Map((board.drivers || []).map((driver) => [driver.driver_id, driver]));
}


function getOrderDraft(orderId, assignment, state) {
  const draft = state.deliveryAssignmentDrafts[orderId] || {};
  return {
    driver_id: Object.prototype.hasOwnProperty.call(draft, "driver_id")
      ? draft.driver_id
      : assignment?.driver_id || "",
    trip_no: Object.prototype.hasOwnProperty.call(draft, "trip_no")
      ? draft.trip_no
      : assignment?.trip_no || "trip1",
  };
}


function createSelect(labelText, value, options, onChange) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const select = document.createElement("select");
  select.value = value || "";
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  });
  select.addEventListener("change", () => onChange(select.value));
  label.append(text, select);
  return label;
}


function createActionButton(label, onClick, { disabled = false, primary = false } = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = primary ? "button-primary workspace-action-button" : "button-secondary workspace-action-button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", onClick);
  return button;
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
  return `${pallets} ${formatPluralLoadUnit("PALLETS", pallets)} - ${bags} ${formatPluralLoadUnit("BAGS", bags)}`;
}


function isBusy(state, actionKey) {
  return state.deliveryBusyActionKey === actionKey;
}
