import { createIcon } from "../utils/icon-utils.js";
import {
  formatOptional,
  formatPluralLoadUnit,
} from "../utils/format-utils.js";


const DELIVERY_TABS = [
  { route: "delivery/task-pool", label: "Task Pool" },
  { route: "delivery/trip-summary", label: "Trip Summary" },
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
      content.append(createDeliveryTaskPool(state.deliveryBoard));
    } else if (state.workspaceRoute === "delivery/trip-summary") {
      content.append(createDeliveryTripSummary(state.deliveryBoard, state, actions));
    } else {
      const savedOnly = state.workspaceRoute === "delivery/history";
      content.append(createRunSheetList(state.deliveryRunSheets, savedOnly, state, actions));
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
  description.textContent = "Plan driver trips, generate Delivery Run Sheets, and review saved history.";
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


function createDeliveryTaskPool(board) {
  if (!board) {
    return createEmptyState("No Delivery workspace data loaded.", "document");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const assignments = assignmentMap(board);
  const unassignedOrders = (board.orders || []).filter(
    (order) => !assignments.has(order.order_id),
  );
  const totalPallets = unassignedOrders.reduce(
    (total, order) => total + Number(order.pallet_quantity || 0),
    0,
  );
  const totalBags = unassignedOrders.reduce(
    (total, order) => total + Number(order.loose_bags_quantity || 0),
    0,
  );

  wrapper.append(
    createMetricGrid([
      ["Unassigned orders", unassignedOrders.length, "document"],
      ["Pallets", totalPallets, "box"],
      ["Loose bags", totalBags, "bag"],
    ]),
  );

  const ordersSection = createSectionHeading(
    "Active Unassigned Delivery Orders",
    "Assign these orders from Trip Summary driver cards.",
  );
  const orderGrid = document.createElement("div");
  orderGrid.className = "workspace-card-grid workspace-order-grid";
  if (!unassignedOrders.length) {
    orderGrid.append(createEmptyState("No unassigned Delivery Orders are available.", "document"));
  } else {
    unassignedOrders.forEach((order) => {
      orderGrid.append(createOrderCard(order));
    });
  }
  wrapper.append(ordersSection, orderGrid);
  return wrapper;
}


function createOrderCard(order) {
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
  appendFact(facts, "Load", formatLoad(order));
  appendFact(facts, "Suburb", order.suburb);

  const products = createProductLines(order);
  card.append(top, facts, products);
  return card;
}


function createDeliveryTripSummary(board, state, actions) {
  if (!board) {
    return createEmptyState("No Delivery workspace data loaded.", "document");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-trip-summary";
  const deliveryDate = scopedDeliveryDate(state);
  wrapper.append(createTripSummaryToolbar(deliveryDate, state, actions));

  const assignments = assignmentMap(board);
  const unassignedOrders = ordersForDeliveryDate(board, deliveryDate).filter(
    (order) => !assignments.has(order.order_id),
  );
  wrapper.append(
    createMetricGrid([
      ["Delivery date", deliveryDate, "calendar"],
      ["Unassigned", unassignedOrders.length, "document"],
      ["Drivers", (board.drivers || []).length, "user"],
    ]),
  );

  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-driver-grid";
  if (!(board.drivers || []).length) {
    grid.append(createEmptyState("No drivers are available for Trip Summary.", "user"));
  } else {
    (board.drivers || []).forEach((driver) => {
      grid.append(createDriverTripSummaryCard(driver, board, deliveryDate, unassignedOrders, state, actions));
    });
  }
  wrapper.append(grid);
  return wrapper;
}


function createTripSummaryToolbar(deliveryDate, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-context-panel workspace-context-panel-delivery";
  const heading = createSectionHeading(
    "Delivery Trip Summary",
    "Choose a delivery date, assign orders to driver trips, select vehicles, and generate run sheets.",
  );
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-delivery-date-control";
  field.textContent = "Delivery date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = deliveryDate;
  input.disabled = state.isDeliveryWorkspaceLoading;
  input.addEventListener("change", () => actions.updateDeliveryTripSummaryDate(input.value));
  field.append(input);
  panel.append(heading, field);
  return panel;
}


function createDriverTripSummaryCard(driver, board, deliveryDate, unassignedOrders, state, actions) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-driver-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const title = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = formatOptional(driver.name, driver.driver_id);
  const badges = document.createElement("div");
  badges.className = "workspace-inline-badges";
  badges.append(createBadge(driver.is_available === false ? "Unavailable" : "Available"));
  if (driver.pallet_only) {
    badges.append(createBadge("Pallet only"));
  }
  title.append(heading, badges);
  top.append(title);
  card.append(top);

  const driverOrders = assignedOrdersForDriver(board, deliveryDate, driver.driver_id);
  const runSheet = findRunSheetForDriver(state.deliveryRunSheets, deliveryDate, driver.driver_id);
  const isLocked = Boolean(runSheet && ["GENERATED", "SAVED"].includes(runSheet.status));
  const totals = orderTotals(driverOrders);
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Pallet total", totals.pallets);
  appendFact(facts, "Loose-bag total", totals.bags);
  appendFact(facts, "Trip 1 orders", driverOrders.filter((item) => item.assignment.trip_no !== "trip2").length);
  appendFact(facts, "Trip 2 orders", driverOrders.filter((item) => item.assignment.trip_no === "trip2").length);
  card.append(facts, createDriverVehicleControl(driver, board, deliveryDate, isLocked, state, actions));

  if (isLocked) {
    card.append(createStatus(
      runSheet.status === "SAVED"
        ? "Saved Delivery Run Sheet locks this driver and delivery date."
        : "Generated Delivery Run Sheet is shown on the Run Sheets page.",
      "loading",
    ));
  }

  card.append(
    createTripPanel("trip1", driver, board, deliveryDate, unassignedOrders, isLocked, state, actions),
    createTripPanel("trip2", driver, board, deliveryDate, unassignedOrders, isLocked, state, actions),
  );

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  if (driverOrders.length && !isLocked) {
    actionsRow.append(createActionButton(
      "Generate Run Sheet",
      () => actions.generateDeliveryRunSheet({ delivery_date: deliveryDate, driver_id: driver.driver_id }),
      {
        disabled: isBusy(state, `delivery-generate:${deliveryDate}:${driver.driver_id}`),
        primary: true,
      },
    ));
  }
  card.append(actionsRow);
  return card;
}


function createDriverVehicleControl(driver, board, deliveryDate, isLocked, state, actions) {
  const section = document.createElement("div");
  section.className = "workspace-context-row workspace-context-row-actions";
  const currentAssignment = findVehicleAssignment(board, deliveryDate, driver.driver_id);
  const draftKey = `${deliveryDate}|${driver.driver_id}`;
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
      deliveryDate,
      driver.driver_id,
      value,
    ),
  );
  vehicleSelect.querySelector("select").disabled = isLocked;
  const applyButton = createActionButton(
    "Save vehicle",
    () => actions.applyDeliveryVehicleAssignment(deliveryDate, driver.driver_id),
    {
      disabled: isLocked || !selectedVehicleId || isBusy(state, `delivery-vehicle:${deliveryDate}:${driver.driver_id}`),
    },
  );
  const clearButton = createActionButton(
    "Clear Vehicle",
    () => actions.clearDeliveryVehicleAssignment(deliveryDate, driver.driver_id),
    {
      disabled: isLocked || !currentAssignment || isBusy(state, `delivery-vehicle-clear:${deliveryDate}:${driver.driver_id}`),
    },
  );
  section.append(vehicleSelect, applyButton, clearButton);
  return section;
}


function createTripPanel(tripNo, driver, board, deliveryDate, unassignedOrders, isLocked, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-trip-panel";
  const title = document.createElement("h4");
  title.textContent = tripNo === "trip2" ? "Trip 2" : "Trip 1";
  panel.append(title);
  const assigned = assignedOrdersForDriver(board, deliveryDate, driver.driver_id).filter(
    (item) => (tripNo === "trip2" ? item.assignment.trip_no === "trip2" : item.assignment.trip_no !== "trip2"),
  );
  if (!assigned.length) {
    panel.append(createEmptyState(`No orders assigned to ${title.textContent}.`, "document"));
  } else {
    assigned.forEach((item) => panel.append(createAssignedOrderRow(item.order, item.assignment, driver, isLocked, state, actions)));
  }
  if (!isLocked) {
    panel.append(createAddOrderControl(deliveryDate, driver, tripNo, unassignedOrders, state, actions));
  }
  return panel;
}


function createAssignedOrderRow(order, assignment, driver, isLocked, state, actions) {
  const row = document.createElement("article");
  row.className = "workspace-record-card workspace-order-row-card";
  const title = document.createElement("div");
  const heading = document.createElement("h5");
  heading.textContent = formatOptional(order.company_name);
  const meta = document.createElement("p");
  meta.textContent = `${formatOptional(order.invoice_number, order.order_id)} - ${formatOptional(order.suburb)} - ${formatLoad(order)}`;
  title.append(heading, meta);
  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  const targetTrip = assignment.trip_no === "trip2" ? "trip1" : "trip2";
  actionsRow.append(
    createActionButton(
      targetTrip === "trip2" ? "Move to Trip 2" : "Move to Trip 1",
      () => actions.moveDeliveryOrderToTrip(order.order_id, driver.driver_id, targetTrip),
      {
        disabled: isLocked || isBusy(state, `delivery-move:${order.order_id}:${targetTrip}`),
      },
    ),
    createActionButton(
      "Unassign",
      () => actions.unassignDeliveryOrder(order.order_id),
      {
        disabled: isLocked || isBusy(state, `delivery-unassign:${order.order_id}`),
      },
    ),
  );
  row.append(title, actionsRow);
  return row;
}


function createAddOrderControl(deliveryDate, driver, tripNo, unassignedOrders, state, actions) {
  const key = `${deliveryDate}|${driver.driver_id}|${tripNo}`;
  const selectedOrderId = state.deliveryTripAddOrderDrafts[key] || "";
  const row = document.createElement("div");
  row.className = "workspace-action-row workspace-add-order-row";
  const select = createSelect(
    "Add Order",
    selectedOrderId,
    [{ value: "", label: "Select unassigned order" }].concat(
      unassignedOrders.map((order) => ({
        value: order.order_id,
        label: `${formatOptional(order.invoice_number, order.order_id)} - ${formatOptional(order.company_name)} - ${formatOptional(order.suburb)}`,
      })),
    ),
    (value) => actions.updateDeliveryTripAddOrderDraft(deliveryDate, driver.driver_id, tripNo, value),
  );
  const button = createActionButton(
    "Add Order",
    () => actions.addDeliveryOrderToTrip(deliveryDate, driver.driver_id, tripNo),
    {
      disabled: !selectedOrderId || isBusy(state, `delivery-add-order:${deliveryDate}:${driver.driver_id}:${tripNo}`),
      primary: true,
    },
  );
  row.append(select, button);
  return row;
}


function createRunSheetList(runSheets, savedOnly, state, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const filtered = (runSheets || []).filter(
    (runSheet) => !savedOnly || runSheet.status === "SAVED",
  );
  wrapper.append(
    createSectionHeading(
      savedOnly ? "Saved Run Sheet History" : "Delivery Run Sheets",
      savedOnly
        ? "Saved Delivery Run Sheets remain viewable and exportable."
        : "Review generated documents, save them, or export saved Daily Run Sheets.",
    ),
  );

  if (savedOnly) {
    wrapper.append(createRunSheetSection("Saved Run Sheets", filtered, state, actions));
    return wrapper;
  }
  wrapper.append(
    createRunSheetSection(
      "Generated Run Sheets",
      filtered.filter((runSheet) => runSheet.status === "GENERATED"),
      state,
      actions,
    ),
    createRunSheetSection(
      "Saved Run Sheets",
      filtered.filter((runSheet) => runSheet.status === "SAVED"),
      state,
      actions,
    ),
  );
  return wrapper;
}


function createRunSheetSection(titleText, runSheets, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-delivery";
  section.append(createSectionHeading(titleText, `${runSheets.length} records`));
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-run-sheet-grid";
  if (!runSheets.length) {
    grid.append(createEmptyState(`No ${titleText.toLowerCase()} for this dispatch date.`, "history"));
  } else {
    runSheets.forEach((runSheet) => grid.append(createRunSheetCard(runSheet, state, actions)));
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
  appendFact(facts, "Delivery date", runSheet.delivery_date);
  appendFact(facts, "Driver", formatOptional(runSheet.driver_name_snapshot, runSheet.driver_id));
  appendFact(facts, "Vehicle", formatOptional(runSheet.vehicle_rego_snapshot, "Not selected"));
  appendFact(facts, "Trip 1 orders", tripCounts.get("trip1") || 0);
  appendFact(facts, "Trip 2 orders", tripCounts.get("trip2") || 0);
  appendFact(facts, "Total pallets", runSheet.total_pallets || 0);
  appendFact(facts, "Total loose bags", runSheet.total_loose_bags || 0);
  appendFact(facts, "Generated", runSheet.generated_at);
  if (runSheet.status === "SAVED") {
    appendFact(facts, "Saved", runSheet.saved_at);
    appendFact(facts, "Saved by", runSheet.saved_by_account_name || "Unknown");
  }
  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  if (runSheet.status === "GENERATED") {
    actionsRow.append(
      createActionButton("Save Run Sheet", () => actions.saveDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-save:${runSheet.run_sheet_id}`),
        primary: true,
      }),
      createActionButton("Cancel Generated", () => actions.cancelDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-cancel:${runSheet.run_sheet_id}`),
      }),
    );
  }
  if (runSheet.status === "SAVED") {
    actionsRow.append(
      createActionButton("Export Daily Run Sheet", () => actions.exportDeliveryRunSheet(runSheet.run_sheet_id), {
        disabled: isBusy(state, `delivery-export:${runSheet.run_sheet_id}`),
        primary: true,
      }),
    );
  }
  card.append(top, facts, createRunSheetPreview(runSheet), actionsRow);
  return card;
}


function createRunSheetPreview(runSheet) {
  const details = document.createElement("details");
  details.className = "workspace-run-sheet-preview";
  const summary = document.createElement("summary");
  summary.textContent = "View Run Sheet details / preview";
  details.append(summary);
  (runSheet.trips || []).forEach((trip) => {
    const title = document.createElement("h4");
    title.textContent = trip.trip_no === "trip2" ? "Trip 2" : "Trip 1";
    const list = document.createElement("ul");
    (trip.orders || []).forEach((order) => {
      const item = document.createElement("li");
      item.textContent = `${formatOptional(order.company_name_snapshot)} - ${formatOptional(order.suburb_snapshot)} - ${formatOptional(order.invoice_number_snapshot, order.task_id)}`;
      list.append(item);
    });
    details.append(title, list);
  });
  return details;
}


function ordersForDeliveryDate(board, deliveryDate) {
  return (board.orders || []).filter((order) => order.delivery_date === deliveryDate);
}


function assignedOrdersForDriver(board, deliveryDate, driverId) {
  const orders = new Map((board.orders || []).map((order) => [order.order_id, order]));
  return (board.assignments || [])
    .filter((assignment) => assignment.driver_id === driverId)
    .map((assignment) => ({ assignment, order: orders.get(assignment.task_id) }))
    .filter((item) => item.order?.delivery_date === deliveryDate)
    .sort((left, right) => {
      const tripCompare = (left.assignment.trip_no || "trip1").localeCompare(right.assignment.trip_no || "trip1");
      if (tripCompare) {
        return tripCompare;
      }
      return formatOptional(left.order.invoice_number, left.order.order_id).localeCompare(
        formatOptional(right.order.invoice_number, right.order.order_id),
      );
    });
}


function findRunSheetForDriver(runSheets, deliveryDate, driverId) {
  return (runSheets || []).find(
    (runSheet) =>
      runSheet.delivery_date === deliveryDate &&
      runSheet.driver_id === driverId &&
      ["GENERATED", "SAVED"].includes(runSheet.status),
  );
}


function findVehicleAssignment(board, deliveryDate, driverId) {
  return (board.driver_vehicle_assignments || []).find(
    (assignment) =>
      assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
  );
}


function assignmentMap(board) {
  return new Map(
    (board.assignments || []).map((assignment) => [assignment.task_id, assignment]),
  );
}


function orderTotals(items) {
  return items.reduce(
    (totals, item) => ({
      pallets: totals.pallets + Number(item.order?.pallet_quantity || 0),
      bags: totals.bags + Number(item.order?.loose_bags_quantity || 0),
    }),
    { pallets: 0, bags: 0 },
  );
}


function scopedDeliveryDate(state) {
  return state.deliveryTripSummaryDate || state.dispatchDate;
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


function createProductLines(order) {
  const products = document.createElement("div");
  products.className = "workspace-product-lines";
  const productTitle = document.createElement("strong");
  productTitle.textContent = "Product details";
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
  return products;
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
  return Boolean(state.deliveryBusyActionKeys?.[actionKey]);
}
