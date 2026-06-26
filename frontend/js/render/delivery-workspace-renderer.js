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
      content.append(createDeliveryTaskPool(state.deliveryBoard, state, actions));
    } else if (state.workspaceRoute === "delivery/trip-summary") {
      content.append(createDeliveryTripSummary(state.deliveryBoard, state, actions));
    } else {
      const savedOnly = state.workspaceRoute === "delivery/history";
      content.append(createRunSheetList(state.deliveryRunSheets, savedOnly, state, actions));
    }
  }

  page.append(content);
  page.append(
    createDeliveryOrderModal(state, actions),
    createDeliveryAttacheImportModal(state, actions),
    createDeliverySpecificationModal(state, actions),
  );
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


function createDeliveryTaskPool(board, state, actions) {
  if (!board) {
    return createEmptyState("No Delivery workspace data loaded.", "document");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const assignments = assignmentMap(board);
  const unassignedOrders = (board.orders || []).filter(
    (order) => !assignments.has(order.order_id),
  );
  const filteredOrders = filterDeliveryTaskPoolOrders(unassignedOrders, state.deliveryTaskPoolFilters);
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

  wrapper.append(createDeliveryTaskPoolActions(actions, state));
  wrapper.append(createDeliveryTaskPoolFilters(unassignedOrders, filteredOrders, state, actions));

  const ordersSection = createSectionHeading(
    "Active Unassigned Delivery Orders",
    "Assign these orders from Trip Summary driver cards.",
  );
  const orderGrid = document.createElement("div");
  orderGrid.className = "workspace-card-grid workspace-order-grid";
  if (!unassignedOrders.length) {
    orderGrid.append(createEmptyState("No unassigned Delivery Orders are available.", "document"));
  } else if (!filteredOrders.length) {
    orderGrid.append(createEmptyState("No unassigned Delivery Orders match the filters.", "document"));
  } else {
    filteredOrders.forEach((order) => {
      orderGrid.append(createOrderCard(order, actions));
    });
  }
  wrapper.append(ordersSection, orderGrid);
  return wrapper;
}


function createDeliveryTaskPoolActions(actions, state) {
  const row = document.createElement("div");
  row.className = "workspace-action-row workspace-task-pool-actions";
  row.append(
    createActionButton("Add Order", actions.openAddDeliveryOrder, {
      primary: true,
      disabled: state.isDeliveryWorkspaceLoading,
    }),
    createActionButton("Import Attache Invoices", actions.openDeliveryAttacheImport, {
      disabled: state.isDeliveryWorkspaceLoading,
    }),
    createActionButton("Driver & Vehicle Specification", actions.openDeliverySpecifications, {
      disabled: state.isDeliveryWorkspaceLoading,
    }),
  );
  return row;
}


function createDeliveryTaskPoolFilters(unassignedOrders, filteredOrders, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-context-panel workspace-delivery-filter-bar";
  const filters = state.deliveryTaskPoolFilters || {};
  const search = createTextInput(
    "Search",
    filters.search || "",
    "Invoice, order #, company, phone, address, suburb, postcode, product, notes",
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
  const count = document.createElement("span");
  count.className = "workspace-filter-count";
  count.textContent = `${filteredOrders.length} of ${unassignedOrders.length} visible`;
  panel.append(search, date, urgency, clear, count);
  return panel;
}


function createOrderCard(order, actions) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-order-card";
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


function filterDeliveryTaskPoolOrders(orders, filters = {}) {
  const search = normalizeSearch(filters.search || "");
  const deliveryDate = filters.delivery_date || "";
  const urgency = filters.urgency || "All";
  return (orders || []).filter((order) => {
    if (deliveryDate && order.delivery_date !== deliveryDate) {
      return false;
    }
    if (urgency && urgency !== "All" && order.urgency !== urgency) {
      return false;
    }
    if (!search) {
      return true;
    }
    return deliveryOrderSearchText(order).includes(search);
  });
}


function deliveryOrderSearchText(order) {
  return normalizeSearch([
    order.invoice_number,
    order.order_no,
    order.company_name,
    order.phone,
    order.delivery_address,
    order.suburb,
    order.postcode,
    order.note,
    ...(order.product_lines || []).map((line) => line.product_name),
  ].filter(Boolean).join(" "));
}


function normalizeSearch(value) {
  return String(value || "").trim().toLowerCase();
}


function hasDeliveryTaskPoolFilters(filters = {}) {
  return Boolean(
    (filters.search || "").trim()
    || filters.delivery_date
    || (filters.urgency && filters.urgency !== "All")
  );
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
  const selectedVehicle = (board.vehicles || []).find(
    (vehicle) => vehicle.vehicle_id === selectedVehicleId,
  );
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
  const vehicleSummary = document.createElement("div");
  vehicleSummary.className = "workspace-vehicle-capacity-summary";
  const selectedVehicleLabel = selectedVehicle?.rego || "Not selected";
  const capacityLabel = selectedVehicle
    ? `${selectedVehicle.pallet_capacity ?? 0} pallets`
    : "Select a vehicle to view";
  vehicleSummary.textContent = `Selected vehicle: ${selectedVehicleLabel} | Capacity: ${capacityLabel}`;
  section.append(vehicleSelect, vehicleSummary, applyButton, clearButton);
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


function createDeliveryOrderModal(state, actions) {
  const formMode = state.deliveryOrderFormMode;
  const order = (state.deliveryBoard?.orders || []).find(
    (item) => item.order_id === state.deliveryOrderDetailId,
  );
  if (!formMode && !order) {
    return document.createDocumentFragment();
  }

  const modal = createWorkspaceModal(
    formMode === "add" ? "Add Delivery Order" : "Delivery Order Detail",
    formMode === "add" ? actions.closeDeliveryOrderModal : actions.closeDeliveryOrderModal,
  );
  const body = modal.querySelector(".workspace-modal-body");
  if (state.deliveryOrderModalError) {
    body.append(createStatus(state.deliveryOrderModalError, "error"));
  }

  if (formMode) {
    body.append(createDeliveryOrderForm(state, actions, formMode));
  } else {
    const locked = isOrderCapturedByRunSheet(order, state.deliveryRunSheets);
    body.append(
      createDeliveryOrderReadOnly(order, state),
      createDeliveryOrderActions(order, locked, state, actions),
    );
  }
  return modal;
}


function createDeliveryOrderReadOnly(order, state) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createSectionHeading("General Information", "Delivery Order details from the scoped Delivery board."));
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid workspace-modal-fact-grid";
  appendFact(facts, "Invoice Number", order.invoice_number);
  appendFact(facts, "Order Number", order.order_no);
  appendFact(facts, "Company Name", order.company_name);
  appendFact(facts, "Phone", order.phone);
  appendFact(facts, "Delivery Address", order.delivery_address);
  appendFact(facts, "Suburb", order.suburb);
  appendFact(facts, "Postcode", order.postcode);
  appendFact(facts, "Delivery Date", order.delivery_date);
  appendFact(facts, "Time Window", [order.start_time, order.end_time].filter(Boolean).join(" - "));
  appendFact(facts, "Zone", order.zone);
  appendFact(facts, "Urgency", order.urgency);
  appendFact(facts, "Preferred Driver", driverName(state.deliveryBoard, order.preferred_driver_id));
  appendFact(facts, "Notes", order.note);
  section.append(facts, createProductLines(order), createLoadSummary(order));
  if (isOrderCapturedByRunSheet(order, state.deliveryRunSheets)) {
    section.append(createStatus("This Delivery Order is captured by a Generated or Saved Delivery Run Sheet. Edit and Cancel are locked.", "loading"));
  }
  return section;
}


function createDeliveryOrderActions(order, locked, state, actions) {
  const row = document.createElement("div");
  row.className = "workspace-action-row";
  row.append(
    createActionButton("Edit Order", () => actions.startEditDeliveryOrder(order.order_id), {
      disabled: locked || isBusy(state, `delivery-order-edit:${order.order_id}`),
      primary: true,
    }),
    createActionButton("Cancel Order", () => actions.cancelActiveDeliveryOrder(order.order_id), {
      disabled: locked || isBusy(state, `delivery-order-cancel:${order.order_id}`),
    }),
  );
  return row;
}


function createDeliveryOrderForm(state, actions, formMode) {
  const form = document.createElement("form");
  form.className = "workspace-modal-section workspace-order-form";
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    actions.saveDeliveryOrderForm();
  });
  const fields = document.createElement("div");
  fields.className = "workspace-form-grid";
  const formState = state.deliveryOrderForm || {};
  [
    ["Invoice Number", "invoice_number"],
    ["Order Number", "order_no"],
    ["Company Name", "company_name"],
    ["Phone", "phone"],
    ["Delivery Address", "delivery_address"],
    ["Suburb", "suburb"],
    ["Postcode", "postcode"],
    ["Delivery Date", "delivery_date", "date"],
    ["Start Time", "start_time", "time"],
    ["End Time", "end_time", "time"],
    ["Zone", "zone"],
    ["Pallet Quantity", "pallet_quantity", "number"],
    ["Loose Bags Quantity", "loose_bags_quantity", "number"],
  ].forEach(([label, field, type]) => {
    fields.append(createBoundInput(label, formState[field], (value) =>
      actions.updateDeliveryOrderForm(field, value), { type: type || "text" }));
  });
  fields.append(createBoundSelect("Urgency", formState.urgency || "Normal", [
    { value: "Normal", label: "Normal" },
    { value: "Urgent", label: "Urgent" },
  ], (value) => actions.updateDeliveryOrderForm("urgency", value)));
  fields.append(createBoundSelect("Preferred Driver", formState.preferred_driver_id || "", [
    { value: "", label: "No preferred driver" },
    ...((state.deliveryBoard?.drivers || []).map((driver) => ({
      value: driver.driver_id,
      label: driver.name,
    }))),
  ], (value) => actions.updateDeliveryOrderForm("preferred_driver_id", value)));
  fields.append(createBoundTextarea("Notes", formState.note || "", (value) =>
    actions.updateDeliveryOrderForm("note", value)));
  form.append(fields, createProductLineEditor(formState.product_lines || [], actions));
  const row = document.createElement("div");
  row.className = "workspace-action-row";
  row.append(
    createActionButton(formMode === "edit" ? "Save Order" : "Add Order", () => actions.saveDeliveryOrderForm(), {
      disabled: isBusy(state, formMode === "edit"
        ? `delivery-order-edit:${state.deliveryOrderDetailId}`
        : "delivery-order-add"),
      primary: true,
    }),
    createActionButton("Cancel editing", formMode === "edit"
      ? actions.cancelDeliveryOrderEdit
      : actions.closeDeliveryOrderModal),
  );
  form.append(row);
  return form;
}


function createProductLineEditor(lines, actions) {
  const section = document.createElement("section");
  section.className = "workspace-product-line-editor";
  const title = document.createElement("h4");
  title.textContent = "Product Lines";
  const list = document.createElement("div");
  list.className = "workspace-product-line-list";
  (lines || []).forEach((line, index) => {
    const row = document.createElement("div");
    row.className = "workspace-product-line-row";
    row.append(
      createBoundInput("Product Name", line.product_name || "", (value) =>
        actions.updateDeliveryOrderProductLine(index, "product_name", value)),
      createBoundInput("Quantity", line.quantity ?? 0, (value) =>
        actions.updateDeliveryOrderProductLine(index, "quantity", value), { type: "number" }),
      createBoundSelect("Unit", line.unit || "PALLETS", [
        { value: "PALLETS", label: "PALLETS" },
        { value: "BAGS", label: "BAGS" },
        { value: "CARTONS", label: "CARTONS" },
      ], (value) => actions.updateDeliveryOrderProductLine(index, "unit", value)),
      createActionButton("Remove", () => actions.removeDeliveryOrderProductLine(index)),
    );
    list.append(row);
  });
  section.append(title, list, createActionButton("Add Product Line", actions.addDeliveryOrderProductLine));
  return section;
}


function createDeliveryAttacheImportModal(state, actions) {
  const importState = state.deliveryAttacheImportState || {};
  if (!importState.isOpen) {
    return document.createDocumentFragment();
  }
  const modal = createWorkspaceModal("Import Attache Invoices", actions.closeDeliveryAttacheImport);
  const body = modal.querySelector(".workspace-modal-body");
  const controls = document.createElement("section");
  controls.className = "workspace-modal-section";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "application/pdf,.pdf";
  fileInput.multiple = true;
  fileInput.addEventListener("change", () => actions.updateDeliveryAttacheImportFiles(fileInput.files));
  const selected = document.createElement("p");
  selected.className = "workspace-muted";
  selected.textContent = `${(importState.files || []).length} PDF file(s) selected`;
  controls.append(fileInput, selected, createActionButton("Preview Import", actions.previewDeliveryAttacheImport, {
    disabled: importState.isPreviewing || !(importState.files || []).length,
    primary: true,
  }));
  body.append(controls);
  if (importState.error) {
    body.append(createStatus(importState.error, "error"));
  }
  if (importState.success) {
    body.append(createStatus(importState.success, "loading"));
  }
  body.append(createDeliveryAttachePreview(importState, actions));
  return modal;
}


function createDeliveryAttachePreview(importState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  if (!(importState.rows || []).length) {
    section.append(createEmptyState("No invoice previews yet.", "document"));
    return section;
  }
  const table = document.createElement("table");
  table.className = "workspace-table workspace-attache-table";
  const header = document.createElement("tr");
  [
    "Import",
    "Invoice",
    "Order",
    "Customer",
    "Phone",
    "Address",
    "Suburb",
    "Postcode",
    "Date",
    "Start",
    "End",
    "Urgency",
    "Pallets",
    "Bags",
    "Notes",
    "Product Lines",
    "Warnings",
  ].forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    header.append(th);
  });
  const thead = document.createElement("thead");
  thead.append(header);
  const tbody = document.createElement("tbody");
  (importState.rows || []).forEach((row) => {
    const tr = document.createElement("tr");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(row.selected);
    checkbox.disabled = importState.isCommitting || row.is_duplicate || !row.importable;
    checkbox.addEventListener("change", () => actions.toggleDeliveryAttacheImportRow(row.row_id, checkbox.checked));
    tr.append(createTableCell(checkbox));
    tr.append(createTableCell(createInlineInput(row.invoice_number, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "invoice_number", value))));
    tr.append(createTableCell(createInlineInput(row.order_no, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "order_no", value))));
    tr.append(createTableCell(createInlineInput(row.company_name, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "company_name", value))));
    tr.append(createTableCell(createInlineInput(row.phone, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "phone", value))));
    tr.append(createTableCell(createInlineInput(row.delivery_address, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_address", value))));
    tr.append(createTableCell(createInlineInput(row.suburb, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "suburb", value))));
    tr.append(createTableCell(createInlineInput(row.postcode, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "postcode", value))));
    tr.append(createTableCell(createInlineInput(row.delivery_date, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_date", value), "date")));
    tr.append(createTableCell(createInlineInput(row.start_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "start_time", value), "time")));
    tr.append(createTableCell(createInlineInput(row.end_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "end_time", value), "time")));
    tr.append(createTableCell(createInlineSelect(row.urgency || "Normal", [
      { value: "Normal", label: "Normal" },
      { value: "Urgent", label: "Urgent" },
    ], (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "urgency", value))));
    tr.append(createTableCell(createInlineInput(row.pallet_quantity, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "pallet_quantity", Number(value || 0)), "number")));
    tr.append(createTableCell(createInlineInput(row.loose_bags_quantity, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "loose_bags_quantity", Number(value || 0)), "number")));
    tr.append(createTableCell(createInlineTextarea(row.note, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "note", value))));
    tr.append(createTableCell(createAttacheProductLineEditor(row, actions)));
    tr.append(createTableCell((row.warnings || []).join("; ")));
    tbody.append(tr);
  });
  table.append(thead, tbody);
  section.append(table, createActionButton("Confirm Import", actions.commitDeliveryAttacheImport, {
    disabled: importState.isCommitting || !(importState.rows || []).some((row) => row.selected),
    primary: true,
  }));
  return section;
}


function createDeliverySpecificationModal(state, actions) {
  if (!state.deliverySpecificationModalOpen) {
    return document.createDocumentFragment();
  }
  const modal = createWorkspaceModal("Driver & Vehicle Specification", actions.closeDeliverySpecifications);
  const body = modal.querySelector(".workspace-modal-body");
  const tabs = document.createElement("div");
  tabs.className = "workspace-action-row";
  tabs.append(
    createActionButton("Drivers", () => actions.setDeliverySpecificationTab("drivers"), {
      primary: state.deliverySpecificationTab !== "vehicles",
    }),
    createActionButton("Vehicles", () => actions.setDeliverySpecificationTab("vehicles"), {
      primary: state.deliverySpecificationTab === "vehicles",
    }),
  );
  body.append(tabs);
  if (state.deliverySpecificationError) {
    body.append(createStatus(state.deliverySpecificationError, "error"));
  }
  body.append(
    state.deliverySpecificationTab === "vehicles"
      ? createVehicleSpecificationPanel(state, actions)
      : createDriverSpecificationPanel(state, actions),
  );
  return modal;
}


function createDriverSpecificationPanel(state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createActionButton("Add Driver", actions.startAddDeliveryDriver, { primary: true }));
  if (state.deliveryDriverForm) {
    section.append(createDriverForm(state, actions));
  }
  const list = document.createElement("div");
  list.className = "workspace-spec-list";
  (state.deliverySpecifications?.drivers || []).forEach((driver) => {
    const row = document.createElement("article");
    row.className = "workspace-record-card";
    row.append(
      document.createTextNode(`${driver.driver_id} - ${driver.name} - ${driver.license_no || ""} - ${driver.email || ""} - ${driver.phone_number || ""}`),
      createSpecAvailability(driver.is_available !== false, (checked) =>
        actions.toggleDeliveryDriverAvailability(driver.driver_id, checked)),
      createActionButton("Edit Driver", () => actions.startEditDeliveryDriver(driver.driver_id)),
      createActionButton("Delete Driver", () => actions.deleteDeliveryDriver(driver.driver_id)),
    );
    list.append(row);
  });
  section.append(list);
  return section;
}


function createVehicleSpecificationPanel(state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createActionButton("Add Vehicle", actions.startAddDeliveryVehicle, { primary: true }));
  if (state.deliveryVehicleForm) {
    section.append(createVehicleForm(state, actions));
  }
  const list = document.createElement("div");
  list.className = "workspace-spec-list";
  (state.deliverySpecifications?.vehicles || []).forEach((vehicle) => {
    const row = document.createElement("article");
    row.className = "workspace-record-card";
    row.append(
      document.createTextNode(`${vehicle.vehicle_id} - ${vehicle.rego} - ${vehicle.type || ""} - ${vehicle.pallet_capacity} pallets`),
      createSpecAvailability(vehicle.is_available !== false, (checked) =>
        actions.toggleDeliveryVehicleAvailability(vehicle.vehicle_id, checked)),
      createActionButton("Edit Vehicle", () => actions.startEditDeliveryVehicle(vehicle.vehicle_id)),
      createActionButton("Delete Vehicle", () => actions.deleteDeliveryVehicle(vehicle.vehicle_id)),
    );
    list.append(row);
  });
  section.append(list);
  return section;
}


function createDriverForm(state, actions) {
  const form = document.createElement("div");
  form.className = "workspace-form-grid";
  const item = state.deliveryDriverForm || {};
  [["Name", "name"], ["License No", "license_no"], ["Email", "email"], ["Phone Number", "phone_number"], ["Start", "start_time", "time"], ["End", "end_time", "time"]].forEach(([label, field, type]) => {
    form.append(createBoundInput(label, item[field], (value) => actions.updateDeliveryDriverForm(field, value), { type: type || "text" }));
  });
  form.append(
    createBoundCheckbox("Available", item.is_available !== false, (value) => actions.updateDeliveryDriverForm("is_available", value)),
    createBoundCheckbox("Pallet Only", Boolean(item.pallet_only), (value) => actions.updateDeliveryDriverForm("pallet_only", value)),
    createActionButton("Save Driver", actions.saveDeliveryDriver, { primary: true }),
    createActionButton("Cancel", actions.cancelDeliveryDriverForm),
  );
  return form;
}


function createVehicleForm(state, actions) {
  const form = document.createElement("div");
  form.className = "workspace-form-grid";
  const item = state.deliveryVehicleForm || {};
  [["Rego", "rego"], ["Type", "type"], ["Pallet Capacity", "pallet_capacity", "number"], ["Tub Capacity", "tub_capacity", "number"], ["Trolley Capacity", "trolley_capacity", "number"], ["Stillage Capacity", "stillage_capacity", "number"]].forEach(([label, field, type]) => {
    form.append(createBoundInput(label, item[field], (value) => actions.updateDeliveryVehicleForm(field, value), { type: type || "text" }));
  });
  form.append(
    createBoundCheckbox("Available", item.is_available !== false, (value) => actions.updateDeliveryVehicleForm("is_available", value)),
    createActionButton("Save Vehicle", actions.saveDeliveryVehicle, { primary: true }),
    createActionButton("Cancel", actions.cancelDeliveryVehicleForm),
  );
  return form;
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


function createBoundInput(labelText, value, onInput, { type = "text" } = {}) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("input");
  input.type = type;
  if (type === "number") {
    input.setAttribute("min", "0");
  }
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  label.append(text, input);
  return label;
}


function createBoundTextarea(labelText, value, onInput) {
  const label = document.createElement("label");
  label.className = "workspace-field workspace-field-wide";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("textarea");
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  label.append(text, input);
  return label;
}


function createBoundSelect(labelText, value, options, onChange) {
  return createSelect(labelText, value, options, onChange);
}


function createBoundCheckbox(labelText, checked, onChange) {
  const label = document.createElement("label");
  label.className = "workspace-field workspace-checkbox-field";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(checked);
  input.addEventListener("change", () => onChange(input.checked));
  label.append(input, document.createTextNode(labelText));
  return label;
}


function createTextInput(labelText, value, placeholder, onInput, { type = "text" } = {}) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("input");
  input.type = type;
  input.value = value || "";
  input.placeholder = placeholder || "";
  input.addEventListener("input", () => onInput(input.value));
  label.append(text, input);
  return label;
}


function createWorkspaceModal(titleText, onClose) {
  const root = document.createElement("div");
  root.className = "workspace-modal-backdrop";
  const modal = document.createElement("article");
  modal.className = "workspace-modal";
  modal.tabIndex = -1;
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.addEventListener("click", (event) => event.stopPropagation());
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  });
  const header = document.createElement("header");
  header.className = "workspace-modal-header";
  const title = document.createElement("h3");
  title.textContent = titleText;
  const close = createActionButton("Close", onClose);
  header.append(title, close);
  const body = document.createElement("div");
  body.className = "workspace-modal-body";
  modal.append(header, body);
  root.append(modal);
  if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
    window.setTimeout(() => modal.focus(), 0);
  }
  return root;
}


function createLoadSummary(order) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createSectionHeading("Load Summary", "Delivery totals remain Delivery Order only."));
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Pallet quantity", order.pallet_quantity);
  appendFact(facts, "Loose bag quantity", order.loose_bags_quantity);
  section.append(facts);
  return section;
}


function isOrderCapturedByRunSheet(order, runSheets) {
  if (!order) {
    return false;
  }
  return (runSheets || []).some((runSheet) =>
    ["GENERATED", "SAVED"].includes(runSheet.status)
    && (runSheet.trips || []).some((trip) =>
      (trip.orders || []).some((snapshot) => snapshot.task_id === order.order_id),
    ),
  );
}


function driverName(board, driverId) {
  if (!driverId) {
    return "No preferred driver";
  }
  return (board?.drivers || []).find((driver) => driver.driver_id === driverId)?.name || driverId;
}


function createTableCell(content) {
  const cell = document.createElement("td");
  if (content && typeof content === "object" && typeof content.nodeType === "number") {
    cell.append(content);
  } else {
    cell.textContent = formatOptional(content, "");
  }
  return cell;
}


function createInlineInput(value, onInput, type = "text") {
  const input = document.createElement("input");
  input.type = type;
  if (type === "number") {
    input.setAttribute("min", "0");
  }
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  return input;
}


function createInlineTextarea(value, onInput) {
  const input = document.createElement("textarea");
  input.className = "workspace-inline-textarea";
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  return input;
}


function createInlineSelect(value, options, onChange) {
  const select = document.createElement("select");
  select.value = value || "";
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  });
  select.addEventListener("change", () => onChange(select.value));
  return select;
}


function createAttacheProductLineEditor(row, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-attache-products";
  (row.product_lines || []).forEach((line, index) => {
    const lineRow = document.createElement("div");
    lineRow.className = "workspace-attache-product-row";
    lineRow.append(
      createInlineInput(line.product_name, (value) =>
        actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "product_name", value)),
      createInlineInput(line.quantity, (value) =>
        actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "quantity", value), "number"),
      createInlineSelect(line.unit || "PALLETS", [
        { value: "PALLETS", label: "PALLETS" },
        { value: "BAGS", label: "BAGS" },
        { value: "CARTONS", label: "CARTONS" },
      ], (value) =>
        actions.updateDeliveryAttacheImportProductLine(row.row_id, index, "unit", value)),
      createActionButton("Remove", () =>
        actions.removeDeliveryAttacheImportProductLine(row.row_id, index)),
    );
    wrapper.append(lineRow);
  });
  if (!(row.product_lines || []).length) {
    const empty = document.createElement("p");
    empty.className = "workspace-muted";
    empty.textContent = "No product lines parsed.";
    wrapper.append(empty);
  }
  wrapper.append(createActionButton("Add Product Line", () =>
    actions.addDeliveryAttacheImportProductLine(row.row_id)));
  return wrapper;
}


function productLineSummary(row) {
  return (row.product_lines || [])
    .map((line) => `${formatOptional(line.product_name)} - ${line.quantity} ${formatPluralLoadUnit(line.unit, line.quantity)}`)
    .join("; ") || "No product lines";
}


function createSpecAvailability(checked, onChange) {
  return createBoundCheckbox("Available", checked, onChange);
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
