import { createIcon } from "../utils/icon-utils.js";
import {
  formatOptional,
  formatPluralLoadUnit,
} from "../utils/format-utils.js";
import {
  formatDeliveryVehicleConflictMessage,
  formatDeliveryVehicleOptionLabel,
  getDeliveryVehicleConflictDriverNames,
} from "../utils/delivery-vehicle-utils.js";
import {
  isDeliveryOrderUrgent,
  normalizeDeliveryOrderUrgency,
  sortDeliveryTaskPoolOrders,
} from "../utils/delivery-order-priority-utils.js";


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
  if (
    state.workspaceRoute === "delivery/trip-summary"
    && state.deliveryGenerationConfirmation
  ) {
    page.append(createDeliveryGenerationConfirmationModal(state, actions));
  }
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
  const filteredOrders = sortDeliveryTaskPoolOrders(
    filterDeliveryTaskPoolOrders(unassignedOrders, state.deliveryTaskPoolFilters),
  );

  wrapper.append(createDeliveryTaskPoolPanel(unassignedOrders, filteredOrders, state, actions));
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
  wrapper.append(orderGrid);
  return wrapper;
}


function createDeliveryTaskPoolPanel(unassignedOrders, filteredOrders, state, actions) {
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
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Order Delivery";
  const title = document.createElement("h3");
  title.textContent = "Delivery Orders";
  const description = document.createElement("p");
  description.textContent = "Filter active unassigned Orders, then assign each Order directly to a Driver and Trip.";
  copy.append(kicker, title, description);
  titleGroup.append(icon, copy);

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-task-pool-actions";
  actionsRow.append(
    createActionButton("Add Order", actions.openAddDeliveryOrder, {
      primary: true,
      disabled: state.isDeliveryWorkspaceLoading,
      iconName: "plus",
    }),
    createActionButton("Import Attache Invoices", actions.openDeliveryAttacheImport, {
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


function createOrderCard(order, board, state, actions) {
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
    createChip(`Delivery Date: ${formatOptional(order.delivery_date)}`),
    createChip(`Start: ${formatOptional(order.start_time, "-")}`),
  );
  const body = document.createElement("div");
  body.className = "workspace-order-card-body";
  const info = document.createElement("div");
  info.className = "workspace-order-card-info";
  info.append(top, chips);
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


function createOrderAssignmentControls(order, board, state, actions) {
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


function filterDeliveryTaskPoolOrders(orders, filters = {}) {
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

  wrapper.append(
    createMetricGrid([
      ["Delivery date", deliveryDate, "calendar"],
      ["Drivers", (board.drivers || []).length, "user"],
    ]),
  );

  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-driver-grid";
  if (!(board.drivers || []).length) {
    grid.append(createEmptyState("No drivers are available for Trip Summary.", "user"));
  } else {
    (board.drivers || []).forEach((driver) => {
      grid.append(createDriverTripSummaryCard(driver, board, deliveryDate, state, actions));
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
    "Review driver trips, manage assigned orders, select vehicles, and generate Delivery Run Sheets.",
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


function createDriverTripSummaryCard(driver, board, deliveryDate, state, actions) {
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
    createTripPanel("trip1", driver, board, deliveryDate, isLocked, state, actions),
    createTripPanel("trip2", driver, board, deliveryDate, isLocked, state, actions),
  );

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  if (driverOrders.length && !isLocked) {
    const generateButton = createActionButton(
      "Generate Run Sheet",
      () => actions.generateDeliveryRunSheet(
        createDeliveryGenerationCandidate(
          driver,
          board,
          deliveryDate,
          driverOrders,
          state,
        ),
      ),
      {
        disabled: isBusy(state, `delivery-generate:${deliveryDate}:${driver.driver_id}`),
        primary: true,
      },
    );
    generateButton.dataset.workspaceGenerate = "delivery";
    generateButton.dataset.driverId = driver.driver_id;
    generateButton.dataset.serviceDate = deliveryDate;
    actionsRow.append(generateButton);
  }
  card.append(actionsRow);
  return card;
}


function createDriverVehicleControl(driver, board, deliveryDate, isLocked, state, actions) {
  const section = document.createElement("div");
  section.className = "workspace-context-row workspace-vehicle-control";
  const currentAssignment = findVehicleAssignment(board, deliveryDate, driver.driver_id);
  const draftKey = `${deliveryDate}|${driver.driver_id}`;
  const selectedVehicleId =
    state.deliveryVehicleDrafts[draftKey] ?? currentAssignment?.vehicle_id ?? "";
  const conflictDriverNames = getDeliveryVehicleConflictDriverNames({
    board,
    claims: state.deliveryVehicleClaims,
    deliveryDate,
    driverId: driver.driver_id,
    vehicleId: selectedVehicleId,
  });
  const localConflictMessage = formatDeliveryVehicleConflictMessage(conflictDriverNames);
  const backendConflictMessage = state.deliveryVehicleErrors?.[draftKey] || "";
  const conflictMessage = localConflictMessage || backendConflictMessage;
  const hasVehicleConflict = Boolean(conflictMessage);
  const isUpdatingVehicle = Boolean(state.deliveryVehiclePendingKeys?.[draftKey]);
  const vehicleSelect = createSelect(
    "Vehicle",
    selectedVehicleId,
    [{ value: "", label: "Select vehicle" }].concat(
      (board.vehicles || []).map((vehicle) => ({
        value: vehicle.vehicle_id,
        label: formatDeliveryVehicleOptionLabel(
          vehicle,
          getDeliveryVehicleConflictDriverNames({
            board,
            claims: state.deliveryVehicleClaims,
            deliveryDate,
            driverId: driver.driver_id,
            vehicleId: vehicle.vehicle_id,
          }),
        ),
      })),
    ),
    (value) => actions.updateDeliveryVehicleSelection(
      deliveryDate,
      driver.driver_id,
      value,
    ),
  );
  const select = vehicleSelect.querySelector("select");
  const warningId = `delivery-vehicle-conflict-${deliveryDate}-${driver.driver_id}`
    .replace(/[^a-zA-Z0-9_-]/g, "-");
  select.disabled = isLocked || isUpdatingVehicle;
  select.classList.toggle("workspace-vehicle-select-invalid", hasVehicleConflict);
  select.setAttribute("aria-invalid", hasVehicleConflict ? "true" : "false");
  if (hasVehicleConflict) {
    select.setAttribute("aria-describedby", warningId);
  }
  section.append(vehicleSelect);
  if (hasVehicleConflict) {
    const warning = document.createElement("p");
    warning.id = warningId;
    warning.className = "workspace-vehicle-conflict-warning";
    warning.setAttribute("role", "alert");
    warning.textContent = conflictMessage;
    section.append(warning);
  }
  if (isUpdatingVehicle) {
    const loading = document.createElement("p");
    loading.className = "workspace-vehicle-update-status";
    loading.setAttribute("role", "status");
    loading.textContent = "Updating vehicle...";
    section.append(loading);
  }
  return section;
}


function createTripPanel(tripNo, driver, board, deliveryDate, isLocked, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-trip-panel";
  const title = document.createElement("h4");
  title.textContent = tripNo === "trip2" ? "Trip 2" : "Trip 1";
  panel.append(title);
  const assigned = assignedOrdersForDriver(board, deliveryDate, driver.driver_id).filter(
    (item) => (tripNo === "trip2" ? item.assignment.trip_no === "trip2" : item.assignment.trip_no !== "trip2"),
  );
  if (!assigned.length) {
    panel.append(createEmptyState("No orders assigned", "document"));
  } else {
    assigned.forEach((item) => panel.append(createAssignedOrderRow(item.order, item.assignment, driver, isLocked, state, actions)));
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


function createRunSheetList(runSheets, savedOnly, state, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const deliveryDate = scopedDeliveryDate(state);
  const filtered = (runSheets || []).filter((runSheet) => (
    savedOnly
      ? runSheet.status === "SAVED"
      : runSheet.delivery_date === deliveryDate
        && ["GENERATED", "SAVED"].includes(runSheet.status)
  ));

  if (savedOnly) {
    wrapper.append(createSectionHeading(
      "Saved Run Sheet History",
      "Saved Delivery Run Sheets remain viewable and exportable.",
    ));
    wrapper.append(createRunSheetSection("Saved Run Sheets", filtered, state, actions));
    return wrapper;
  }
  wrapper.append(createRunSheetToolbar(deliveryDate, filtered, state, actions));
  wrapper.append(
    createRunSheetSection(
      "Generated Run Sheets",
      filtered.filter((runSheet) => runSheet.status === "GENERATED"),
      state,
      actions,
      { dailyPreview: true },
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


function createRunSheetToolbar(deliveryDate, runSheets, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-context-panel workspace-context-panel-delivery workspace-run-sheet-toolbar";
  panel.append(createSectionHeading(
    "Delivery Run Sheets",
    "Review generated documents, save them, or export the selected Delivery Date.",
  ));
  const controls = document.createElement("div");
  controls.className = "workspace-run-sheet-toolbar-controls";
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-delivery-date-control";
  field.textContent = "Delivery date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = deliveryDate;
  input.disabled = state.isDeliveryWorkspaceLoading;
  input.addEventListener("change", () => actions.updateDeliveryTripSummaryDate(input.value));
  field.append(input);
  const exportKey = `delivery-export-date:${deliveryDate}`;
  const isExporting = isBusy(state, exportKey);
  const exportButton = createActionButton(
    isExporting ? "Preparing Excel File..." : "Export Excel File",
    () => actions.exportDeliveryRunSheets(deliveryDate),
    {
      disabled: isExporting || !runSheets.length,
    },
  );
  exportButton.dataset.deliveryRunSheetExport = deliveryDate;
  controls.append(field, exportButton);
  panel.append(controls);
  return panel;
}


function createRunSheetSection(
  titleText,
  runSheets,
  state,
  actions,
  { dailyPreview = false } = {},
) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-delivery";
  section.append(createSectionHeading(titleText, `${runSheets.length} records`));
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-run-sheet-grid";
  if (dailyPreview) {
    grid.classList.add("workspace-daily-run-sheet-list");
  }
  if (!runSheets.length) {
    grid.append(createEmptyState(`No ${titleText.toLowerCase()} for this Delivery Date.`, "history"));
  } else {
    runSheets.forEach((runSheet) => grid.append(
      dailyPreview
        ? createGeneratedDailyRunSheet(runSheet, state, actions)
        : createRunSheetCard(runSheet, state, actions),
    ));
  }
  section.append(grid);
  return section;
}


function createGeneratedDailyRunSheet(runSheet, state, actions) {
  const paper = document.createElement("article");
  paper.className = "workspace-daily-run-sheet";

  const header = document.createElement("header");
  header.className = "workspace-daily-run-sheet-header";
  header.append(
    createDailyRunSheetHeaderField("DATE:", formatDailyRunSheetDate(runSheet.delivery_date)),
    createDailyRunSheetTitle(),
    createDailyRunSheetHeaderField(
      "DRIVER:",
      formatOptional(runSheet.driver_name_snapshot, runSheet.driver_id),
      "workspace-daily-run-sheet-driver",
    ),
  );

  const metadata = document.createElement("div");
  metadata.className = "workspace-daily-run-sheet-metadata";
  const vehicle = document.createElement("span");
  vehicle.textContent = runSheet.vehicle_rego_snapshot
    ? `Vehicle: ${runSheet.vehicle_rego_snapshot}`
    : "Vehicle: Not selected";
  const generated = document.createElement("span");
  generated.textContent = `Generated: ${formatOptional(runSheet.generated_at)}`;
  metadata.append(vehicle, generated, createBadge("GENERATED", "generated"));

  const operationalFields = document.createElement("div");
  operationalFields.className = "workspace-daily-run-sheet-operational-fields";
  [
    "START TIME: ______________________",
    "TIME LOADING STARTED (TO BE FILLED IN BY STOREMAN): ______________________",
    "TIME LOADING COMPLETED (TO BE FILLED IN BY STOREMAN): ______________________",
  ].forEach((label) => {
    const field = document.createElement("p");
    field.textContent = label;
    operationalFields.append(field);
  });

  const tableRegion = document.createElement("div");
  tableRegion.className = "workspace-daily-run-sheet-table-scroll";
  tableRegion.tabIndex = 0;
  tableRegion.setAttribute("aria-label", "Daily Run Sheet order table");
  const table = document.createElement("table");
  table.className = "workspace-daily-run-sheet-table";
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  DAILY_RUN_SHEET_COLUMNS.forEach((column) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = column;
    headerRow.append(cell);
  });
  head.append(headerRow);
  const body = document.createElement("tbody");
  dailyRunSheetSnapshotRows(runSheet).forEach((order) => {
    const row = document.createElement("tr");
    dailyRunSheetRowValues(order).forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    body.append(row);
  });
  table.append(head, body);
  tableRegion.append(table);

  const finish = document.createElement("p");
  finish.className = "workspace-daily-run-sheet-finish";
  finish.textContent = "FINISH TIME: ______________________";

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-daily-run-sheet-actions";
  actionsRow.append(
    createActionButton(
      "Save Run Sheet",
      () => actions.saveDeliveryRunSheet(runSheet.run_sheet_id),
      {
        disabled: isBusy(state, `delivery-save:${runSheet.run_sheet_id}`),
        primary: true,
      },
    ),
    createActionButton(
      "Cancel Generated",
      () => actions.cancelDeliveryRunSheet(runSheet.run_sheet_id),
      {
        disabled: isBusy(state, `delivery-cancel:${runSheet.run_sheet_id}`),
      },
    ),
  );
  paper.append(header, metadata, operationalFields, tableRegion, finish, actionsRow);
  return paper;
}


const DAILY_RUN_SHEET_COLUMNS = [
  "Customer Name",
  "Suburb",
  "Invoice #",
  "BAGS",
  "KGS",
  "Pallets",
];


function createDailyRunSheetHeaderField(labelText, valueText, className = "") {
  const field = document.createElement("div");
  field.className = `workspace-daily-run-sheet-header-field ${className}`.trim();
  const label = document.createElement("span");
  label.textContent = labelText;
  const value = document.createElement("strong");
  value.textContent = valueText;
  field.append(label, value);
  return field;
}


function createDailyRunSheetTitle() {
  const title = document.createElement("h3");
  title.className = "workspace-daily-run-sheet-title";
  title.textContent = "DAILY RUN SHEET";
  return title;
}


function dailyRunSheetSnapshotRows(runSheet) {
  return (runSheet.trips || []).flatMap((trip) => trip.orders || []);
}


function dailyRunSheetRowValues(order) {
  return [
    formatOptional(order.company_name_snapshot, ""),
    formatOptional(order.suburb_snapshot, ""),
    formatOptional(order.invoice_number_snapshot || order.order_no_snapshot, ""),
    formatRunSheetNumber(order.loose_bags_quantity_snapshot),
    "",
    formatRunSheetNumber(order.pallet_quantity_snapshot),
  ];
}


function formatRunSheetNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? String(numericValue) : "";
}


function formatDailyRunSheetDate(value) {
  const [year, month, day] = String(value || "").split("-");
  return year && month && day ? `${day}/${month}/${year}` : "";
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
    formMode === "add"
      ? "Add Delivery Order"
      : formMode === "edit"
        ? "Edit Delivery Order"
        : `Delivery Order ${formatOptional(order?.invoice_number, order?.order_no)}`,
    actions.closeDeliveryOrderModal,
    {
      eyebrow: "Delivery Order",
      subtitle: formMode
        ? "Enter customer, delivery, load, product, and note details."
        : `${formatOptional(order?.company_name)}${order?.urgency ? ` - ${order.urgency}` : ""}`,
      iconName: "document",
      width: "order",
    },
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
      createDeliveryOrderActions(order, locked, state, actions),
      locked
        ? createStatus("This Delivery Order is captured by a Generated or Saved Delivery Run Sheet. Edit and Cancel are locked.", "loading")
        : document.createDocumentFragment(),
      createDeliveryOrderReadOnly(order, state),
    );
  }
  return modal;
}


function createDeliveryOrderReadOnly(order, state) {
  const fragment = document.createDocumentFragment();
  fragment.append(
    createModalFactSection("General Information", [
      ["Invoice Number", order.invoice_number],
      ["Order Number", order.order_no],
      ["Company Name", order.company_name],
      ["Phone", order.phone],
      ["Preferred Driver", driverName(state.deliveryBoard, order.preferred_driver_id)],
    ]),
    createModalFactSection("Delivery Details", [
      ["Delivery Address", order.delivery_address],
      ["Suburb", order.suburb],
      ["Postcode", order.postcode],
      ["Delivery Date", order.delivery_date],
      ["Start Time", order.start_time],
      ["End Time", order.end_time],
      ["Zone", order.zone],
      ["Urgency", order.urgency],
    ]),
    createLoadSummary(order),
    createProductLines(order),
    createModalFactSection("Notes", [["Notes", order.note]]),
  );
  return fragment;
}


function createDeliveryOrderActions(order, locked, state, actions) {
  const row = document.createElement("div");
  row.className = "workspace-modal-action-bar";
  row.append(
    createActionButton("Close", actions.closeDeliveryOrderModal, {
      className: "workspace-modal-action-button workspace-modal-action-neutral",
    }),
    createActionButton("Edit Order", () => actions.startEditDeliveryOrder(order.order_id), {
      disabled: locked || isBusy(state, `delivery-order-edit:${order.order_id}`),
      primary: true,
      iconName: "edit",
      className: "workspace-modal-action-button workspace-modal-action-primary",
    }),
    createActionButton("Cancel Order", () => actions.cancelActiveDeliveryOrder(order.order_id), {
      disabled: locked || isBusy(state, `delivery-order-cancel:${order.order_id}`),
      iconName: "trash",
      className: "workspace-modal-action-button workspace-modal-action-danger",
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
  const formState = state.deliveryOrderForm || {};
  form.append(
    createFormSection("Customer Information", [
      createBoundInput("Invoice Number", formState.invoice_number, (value) =>
        actions.updateDeliveryOrderForm("invoice_number", value)),
      createBoundInput("Order Number", formState.order_no, (value) =>
        actions.updateDeliveryOrderForm("order_no", value)),
      createBoundInput("Company Name", formState.company_name, (value) =>
        actions.updateDeliveryOrderForm("company_name", value)),
      createBoundInput("Phone", formState.phone, (value) =>
        actions.updateDeliveryOrderForm("phone", value)),
    ]),
    createFormSection("Delivery Requirements", [
      createBoundInput("Delivery Address", formState.delivery_address, (value) =>
        actions.updateDeliveryOrderForm("delivery_address", value)),
      createBoundInput("Suburb", formState.suburb, (value) =>
        actions.updateDeliveryOrderForm("suburb", value)),
      createBoundInput("Postcode", formState.postcode, (value) =>
        actions.updateDeliveryOrderForm("postcode", value)),
      createBoundInput("Delivery Date", formState.delivery_date, (value) =>
        actions.updateDeliveryOrderForm("delivery_date", value), { type: "date" }),
      createBoundInput("Start Time", formState.start_time, (value) =>
        actions.updateDeliveryOrderForm("start_time", value), { type: "time" }),
      createBoundInput("End Time", formState.end_time, (value) =>
        actions.updateDeliveryOrderForm("end_time", value), { type: "time" }),
      createBoundInput("Zone", formState.zone, (value) =>
        actions.updateDeliveryOrderForm("zone", value)),
      createBoundSelect("Urgency", formState.urgency || "Normal", [
        { value: "Normal", label: "Normal" },
        { value: "Urgent", label: "Urgent" },
      ], (value) => actions.updateDeliveryOrderForm("urgency", value)),
      createBoundSelect("Preferred Driver", formState.preferred_driver_id || "", [
        { value: "", label: "No preferred driver" },
        ...((state.deliveryBoard?.drivers || []).map((driver) => ({
          value: driver.driver_id,
          label: driver.name,
        }))),
      ], (value) => actions.updateDeliveryOrderForm("preferred_driver_id", value)),
    ]),
    createFormSection("Load and Product Lines", [
      createBoundInput("Pallet Quantity", formState.pallet_quantity, (value) =>
        actions.updateDeliveryOrderForm("pallet_quantity", value), { type: "number" }),
      createBoundInput("Loose Bags Quantity", formState.loose_bags_quantity, (value) =>
        actions.updateDeliveryOrderForm("loose_bags_quantity", value), { type: "number" }),
      createProductLineEditor(formState.product_lines || [], actions),
    ]),
    createFormSection("Notes", [
      createBoundTextarea("Notes", formState.note || "", (value) =>
        actions.updateDeliveryOrderForm("note", value)),
    ]),
  );
  const row = document.createElement("footer");
  row.className = "workspace-modal-footer";
  row.append(
    createActionButton("Cancel", formMode === "edit"
      ? actions.cancelDeliveryOrderEdit
      : actions.closeDeliveryOrderModal),
    createActionButton(formMode === "edit" ? "Save Changes" : "Create Order", () => actions.saveDeliveryOrderForm(), {
      disabled: isBusy(state, formMode === "edit"
        ? `delivery-order-edit:${state.deliveryOrderDetailId}`
        : "delivery-order-add"),
      primary: true,
      iconName: "document",
    }),
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
  const modal = createWorkspaceModal(
    "Import Attache Invoices",
    actions.closeDeliveryAttacheImport,
    {
      eyebrow: "Delivery Order Import",
      subtitle: "Upload PDF invoices, review extracted values, then confirm selected imports.",
      iconName: "cloud-upload",
      width: "import",
    },
  );
  const body = modal.querySelector(".workspace-modal-body");
  if (importState.error) {
    body.append(createStatus(importState.error, "error"));
  }
  if (importState.success) {
    body.append(createStatus(importState.success, "loading"));
  }
  if ((importState.step || "files") === "review") {
    body.append(createDeliveryAttachePreview(importState, actions));
  } else {
    body.append(createDeliveryAttacheFileStep(importState, actions));
  }
  return modal;
}


function createDeliveryAttacheFileStep(importState, actions) {
  const controls = document.createElement("section");
  controls.className = "workspace-modal-section workspace-attache-file-step";
  controls.append(createSectionHeading("Step 1: Select PDF invoices", "PDF invoices only. Choose one or more Attache invoice PDFs."));
  const dropZone = document.createElement("div");
  dropZone.className = "workspace-attache-dropzone";
  let dragDepth = 0;
  const setDragActive = (active) => {
    dropZone.classList.toggle("workspace-attache-dropzone-active", active);
  };
  dropZone.addEventListener("dragenter", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepth += 1;
    setDragActive(true);
  });
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "copy";
    }
    setDragActive(true);
  });
  dropZone.addEventListener("dragleave", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) {
      setDragActive(false);
    }
  });
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepth = 0;
    setDragActive(false);
    actions.updateDeliveryAttacheImportFiles(event.dataTransfer?.files || [], {
      source: "drop",
    });
  });
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "application/pdf,.pdf";
  fileInput.multiple = true;
  fileInput.className = "visually-hidden-file-input";
  fileInput.id = "delivery-attache-file-input";
  fileInput.addEventListener("change", () => actions.updateDeliveryAttacheImportFiles(fileInput.files));
  const fileButton = document.createElement("label");
  fileButton.className = "button-secondary workspace-action-button workspace-file-select-button";
  fileButton.setAttribute("for", fileInput.id);
  fileButton.append(createIcon("document"), document.createTextNode("Choose PDF files"));
  const selected = document.createElement("strong");
  selected.textContent = `${(importState.files || []).length} file${(importState.files || []).length === 1 ? "" : "s"} selected`;
  const helper = document.createElement("p");
  helper.className = "workspace-muted";
  helper.textContent = "Drop PDF files here, or use Choose PDF files.";
  dropZone.append(fileInput, fileButton, selected, helper);
  const fileList = document.createElement("div");
  fileList.className = "workspace-attache-file-list";
  (importState.files || []).forEach((file, index) => {
    const chip = document.createElement("span");
    chip.className = "workspace-file-chip";
    chip.append(document.createTextNode(file.name || `PDF ${index + 1}`));
    chip.append(createActionButton("Remove", () => actions.removeDeliveryAttacheImportFile(index), {
      disabled: importState.isPreviewing,
      className: "workspace-file-chip-remove",
    }));
    fileList.append(chip);
  });
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer";
  footer.append(
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton("Preview Import", actions.previewDeliveryAttacheImport, {
      iconName: "view",
      primary: true,
      disabled: importState.isPreviewing || !(importState.files || []).length,
    }),
  );
  controls.append(dropZone, fileList, footer);
  return controls;
}


function createDeliveryAttachePreview(importState, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-attache-review-step";
  const rows = importState.rows || [];
  section.append(createSectionHeading("Step 2: Review extracted invoices", "Check parsed values, expand rows for edits, then confirm selected imports."));
  if (!rows.length) {
    section.append(createEmptyState("No invoice previews yet.", "document"));
    return section;
  }
  section.append(createAttacheSummaryStrip(rows));
  const selectionRow = document.createElement("div");
  selectionRow.className = "workspace-action-row workspace-attache-selection-row";
  selectionRow.append(
    createActionButton("Select all ready", actions.selectAllReadyDeliveryAttacheRows),
    createActionButton("Clear selection", actions.clearDeliveryAttacheImportSelection),
  );
  const list = document.createElement("div");
  list.className = "workspace-attache-review-list";
  rows.forEach((row) => {
    list.append(createAttacheReviewRow(row, importState, actions));
  });
  const selectedCount = rows.filter((row) => row.selected && row.importable && !row.is_duplicate).length;
  const footer = document.createElement("footer");
  footer.className = "workspace-modal-footer workspace-modal-footer-sticky";
  footer.append(
    createActionButton("Back to files", actions.backDeliveryAttacheImportToFiles),
    createActionButton("Cancel", actions.closeDeliveryAttacheImport),
    createActionButton(`Confirm Import (${selectedCount} selected)`, actions.commitDeliveryAttacheImport, {
      disabled: importState.isCommitting || selectedCount === 0,
      primary: true,
      iconName: "cloud-upload",
    }),
  );
  section.append(selectionRow, list, footer);
  return section;
}


function createAttacheSummaryStrip(rows) {
  const ready = rows.filter((row) => row.importable && !row.is_duplicate && !(row.warnings || []).length).length;
  const duplicates = rows.filter((row) => row.is_duplicate).length;
  const warnings = rows.filter((row) => (row.warnings || []).length || !row.importable).length;
  const selected = rows.filter((row) => row.selected && row.importable && !row.is_duplicate).length;
  const strip = document.createElement("div");
  strip.className = "workspace-attache-summary-strip";
  [
    ["Total files", rows.length],
    ["Ready to import", ready],
    ["Duplicates", duplicates],
    ["Warnings / parse issues", warnings],
    ["Selected for import", selected],
  ].forEach(([label, value]) => {
    strip.append(createMetricPill(label, value));
  });
  return strip;
}


function createAttacheReviewRow(row, importState, actions) {
  const card = document.createElement("article");
  card.className = "workspace-attache-review-card";
  const expanded = Boolean((importState.expandedRowIds || {})[row.row_id]);
  const status = attacheRowStatus(row);
  const header = document.createElement("div");
  header.className = "workspace-attache-review-header";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = Boolean(row.selected);
  checkbox.disabled = importState.isCommitting || row.is_duplicate || !row.importable;
  checkbox.addEventListener("change", () => actions.toggleDeliveryAttacheImportRow(row.row_id, checkbox.checked));
  const summary = document.createElement("div");
  summary.className = "workspace-attache-review-summary";
  summary.append(
    createBadge(status),
    createInlineMeta("Invoice", row.invoice_number),
    createInlineMeta("Order", row.order_no),
    createInlineMeta("Customer", row.company_name),
    createInlineMeta("Delivery Date", row.delivery_date),
    createInlineMeta("Load", `${row.pallet_quantity || 0} pallets / ${row.loose_bags_quantity || 0} bags`),
  );
  const warning = document.createElement("p");
  warning.className = "workspace-attache-warning-summary";
  warning.textContent = row.is_duplicate
    ? "Duplicate invoice already exists and cannot be selected."
    : (row.warnings || []).join("; ");
  const expand = createActionButton(expanded ? "Collapse" : "Expand", () =>
    actions.toggleDeliveryAttacheImportExpanded(row.row_id));
  header.append(checkbox, summary, expand);
  card.append(header);
  if (warning.textContent) {
    card.append(warning);
  }
  if (expanded) {
    card.append(createAttacheExpandedEditor(row, actions));
  }
  return card;
}


function createAttacheExpandedEditor(row, actions) {
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-attache-expanded-editor";
  wrapper.append(
    createFormSection("Customer and Invoice", [
      createInlineField("Invoice Number", createInlineInput(row.invoice_number, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "invoice_number", value))),
      createInlineField("Order Number", createInlineInput(row.order_no, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "order_no", value))),
      createInlineField("Company Name", createInlineInput(row.company_name, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "company_name", value))),
      createInlineField("Phone", createInlineInput(row.phone, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "phone", value))),
    ]),
    createFormSection("Delivery Details", [
      createInlineField("Delivery Address", createInlineInput(row.delivery_address, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_address", value))),
      createInlineField("Suburb", createInlineInput(row.suburb, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "suburb", value))),
      createInlineField("Postcode", createInlineInput(row.postcode, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "postcode", value))),
      createInlineField("Delivery Date", createInlineInput(row.delivery_date, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "delivery_date", value), "date")),
      createInlineField("Start Time", createInlineInput(row.start_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "start_time", value), "time")),
      createInlineField("End Time", createInlineInput(row.end_time, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "end_time", value), "time")),
      createInlineField("Urgency", createInlineSelect(row.urgency || "Normal", [
        { value: "Normal", label: "Normal" },
        { value: "Urgent", label: "Urgent" },
      ], (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "urgency", value))),
    ]),
    createFormSection("Load", [
      createInlineField("Pallet Quantity", createInlineInput(row.pallet_quantity, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "pallet_quantity", Number(value || 0)), "number")),
      createInlineField("Loose Bags Quantity", createInlineInput(row.loose_bags_quantity, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "loose_bags_quantity", Number(value || 0)), "number")),
    ]),
    createFormSection("Product Lines", [createAttacheProductLineEditor(row, actions)]),
    createFormSection("Notes", [createInlineField("Notes", createInlineTextarea(row.note, (value) => actions.updateDeliveryAttacheImportRow(row.row_id, "note", value)))]),
  );
  return wrapper;
}


function attacheRowStatus(row) {
  if (!row.importable) {
    return "Not importable";
  }
  if (row.is_duplicate) {
    return "Duplicate";
  }
  if ((row.warnings || []).length) {
    return "Warning";
  }
  return "Ready";
}


function createInlineMeta(labelText, value) {
  const item = document.createElement("span");
  item.className = "workspace-inline-meta";
  item.textContent = `${labelText}: ${formatOptional(value)}`;
  return item;
}


function createMetricPill(labelText, value) {
  const pill = document.createElement("span");
  pill.className = "workspace-metric-pill";
  pill.textContent = `${labelText}: ${value}`;
  return pill;
}


function createInlineField(labelText, control) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  label.append(text, control);
  return label;
}


function createDeliverySpecificationModal(state, actions) {
  if (!state.deliverySpecificationModalOpen) {
    return document.createDocumentFragment();
  }
  const modal = createWorkspaceModal(
    "Driver & Vehicle Specification",
    actions.closeDeliverySpecifications,
    {
      eyebrow: "Delivery Specification",
      subtitle: "Manage shared driver and vehicle records used by Order Delivery.",
      iconName: "truck",
      width: "specification",
    },
  );
  const body = modal.querySelector(".workspace-modal-body");
  const tabs = document.createElement("div");
  tabs.className = "workspace-action-row workspace-spec-tabs";
  const driverCount = (state.deliverySpecifications?.drivers || []).length;
  const vehicleCount = (state.deliverySpecifications?.vehicles || []).length;
  tabs.append(
    createActionButton(`Drivers (${driverCount})`, () => actions.setDeliverySpecificationTab("drivers"), {
      primary: state.deliverySpecificationTab !== "vehicles",
    }),
    createActionButton(`Vehicles (${vehicleCount})`, () => actions.setDeliverySpecificationTab("vehicles"), {
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
  const wrap = document.createElement("div");
  wrap.className = "workspace-spec-table-wrap";
  const drivers = state.deliverySpecifications?.drivers || [];
  if (!drivers.length) {
    wrap.append(createEmptyState("No Drivers available.", "user"));
    section.append(wrap);
    return section;
  }
  const table = document.createElement("table");
  table.className = "workspace-table workspace-spec-table";
  table.append(createTableHeader([
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
  const body = document.createElement("tbody");
  drivers.forEach((driver) => {
    const row = document.createElement("tr");
    row.append(
      createTableCell(createSpecAvailability(driver.is_available !== false, (checked) =>
        actions.toggleDeliveryDriverAvailability(driver.driver_id, checked))),
      createTableCell(driver.driver_id),
      createTableCell(driver.name),
      createTableCell(driver.license_no),
      createTableCell(driver.email),
      createTableCell(driver.phone_number),
      createTableCell(driver.start_time),
      createTableCell(driver.end_time),
      createTableCell(driver.pallet_only ? "Yes" : "No"),
      createTableCell(createSpecActionGroup(
        createActionButton("Edit", () => actions.startEditDeliveryDriver(driver.driver_id)),
        createActionButton("Delete", () => actions.deleteDeliveryDriver(driver.driver_id), {
          className: "workspace-modal-action-danger",
        }),
      )),
    );
    body.append(row);
  });
  table.append(body);
  wrap.append(table);
  section.append(wrap);
  return section;
}


function createVehicleSpecificationPanel(state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createActionButton("Add Vehicle", actions.startAddDeliveryVehicle, { primary: true }));
  if (state.deliveryVehicleForm) {
    section.append(createVehicleForm(state, actions));
  }
  const wrap = document.createElement("div");
  wrap.className = "workspace-spec-table-wrap";
  const vehicles = state.deliverySpecifications?.vehicles || [];
  if (!vehicles.length) {
    wrap.append(createEmptyState("No Vehicles available.", "truck"));
    section.append(wrap);
    return section;
  }
  const table = document.createElement("table");
  table.className = "workspace-table workspace-spec-table";
  table.append(createTableHeader([
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
  const body = document.createElement("tbody");
  vehicles.forEach((vehicle) => {
    const row = document.createElement("tr");
    row.append(
      createTableCell(createSpecAvailability(vehicle.is_available !== false, (checked) =>
        actions.toggleDeliveryVehicleAvailability(vehicle.vehicle_id, checked))),
      createTableCell(vehicle.vehicle_id),
      createTableCell(vehicle.rego),
      createTableCell(vehicle.type),
      createTableCell(vehicle.pallet_capacity),
      createTableCell(vehicle.tub_capacity),
      createTableCell(vehicle.trolley_capacity),
      createTableCell(vehicle.stillage_capacity),
      createTableCell(createSpecActionGroup(
        createActionButton("Edit", () => actions.startEditDeliveryVehicle(vehicle.vehicle_id)),
        createActionButton("Delete", () => actions.deleteDeliveryVehicle(vehicle.vehicle_id), {
          className: "workspace-modal-action-danger",
        }),
      )),
    );
    body.append(row);
  });
  table.append(body);
  wrap.append(table);
  section.append(wrap);
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


function createDeliveryGenerationCandidate(
  driver,
  board,
  deliveryDate,
  driverOrders,
  state,
) {
  const vehicleAssignment = findVehicleAssignment(board, deliveryDate, driver.driver_id);
  const vehicleDraftKey = `${deliveryDate}|${driver.driver_id}`;
  const vehicleId = state.deliveryVehicleDrafts?.[vehicleDraftKey]
    ?? vehicleAssignment?.vehicle_id
    ?? "";
  const vehicle = (board.vehicles || []).find((item) => item.vehicle_id === vehicleId);
  const totals = orderTotals(driverOrders);
  const orders = driverOrders.map(({ order, assignment }) => ({
    order_id: order.order_id,
    order_number: order.order_no || order.invoice_number || order.order_id,
    company_name: order.company_name,
    suburb: order.suburb,
    delivery_date: order.delivery_date,
    trip_no: assignment.trip_no === "trip2" ? "trip2" : "trip1",
    pallet_quantity: Number(order.pallet_quantity || 0),
    loose_bags_quantity: Number(order.loose_bags_quantity || 0),
    carton_quantity: (order.product_lines || []).reduce(
      (total, line) => total + (line.unit === "CARTONS" ? Number(line.quantity || 0) : 0),
      0,
    ),
  }));
  return {
    delivery_date: deliveryDate,
    driver_id: driver.driver_id,
    driver_name: formatOptional(driver.name, driver.driver_id),
    vehicle: vehicle
      ? { rego: vehicle.rego, pallet_capacity: vehicle.pallet_capacity }
      : null,
    orders,
    totals: {
      ...totals,
      cartons: orders.reduce((total, order) => total + order.carton_quantity, 0),
      trip1: orders.filter((order) => order.trip_no === "trip1").length,
      trip2: orders.filter((order) => order.trip_no === "trip2").length,
    },
  };
}


function createDeliveryGenerationConfirmationModal(state, actions) {
  const confirmation = state.deliveryGenerationConfirmation;
  const actionKey = `delivery-generate:${confirmation.delivery_date}:${confirmation.driver_id}`;
  const isGenerating = isBusy(state, actionKey);
  const modal = createWorkspaceModal(
    "Confirm Delivery Run Sheet",
    actions.closeDeliveryGenerationConfirmation,
    {
      eyebrow: "Order Delivery",
      subtitle: "Review the captured driver, date, vehicle, orders, and totals before generating.",
      iconName: "document",
      width: "confirmation",
      closeDisabled: isGenerating,
    },
  );
  const body = modal.querySelector(".workspace-modal-body");
  body.classList.add("workspace-generation-confirmation-body");
  body.append(createModalFactSection("Run Sheet Summary", [
    ["Driver", confirmation.driver_name],
    ["Dispatch date", confirmation.dispatch_date],
    ["Delivery date", confirmation.delivery_date],
    ["Vehicle", confirmation.vehicle?.rego || "Not selected"],
    [
      "Vehicle capacity",
      confirmation.vehicle
        ? `${formatOptional(confirmation.vehicle.pallet_capacity, 0)} pallets`
        : "Select a vehicle to view",
    ],
    ["Orders", confirmation.orders.length],
    ["Trip 1 orders", confirmation.totals.trip1 || 0],
    ["Trip 2 orders", confirmation.totals.trip2 || 0],
    ["Pallets", confirmation.totals.pallets || 0],
    ["Loose bags", confirmation.totals.bags || 0],
    ["Cartons", confirmation.totals.cartons || 0],
  ]));

  const preview = document.createElement("section");
  preview.className = "workspace-generation-preview";
  preview.append(createSectionHeading(
    "Assigned Delivery Orders",
    `${confirmation.orders.length} ${confirmation.orders.length === 1 ? "order" : "orders"} will be captured by the backend if still eligible.`,
  ));
  const list = document.createElement("div");
  list.className = "workspace-generation-preview-list";
  confirmation.orders.forEach((order) => {
    const row = document.createElement("article");
    row.className = "workspace-generation-preview-row";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = `${formatOptional(order.order_number)} - ${formatOptional(order.company_name)}`;
    const location = document.createElement("span");
    location.textContent = `${formatOptional(order.suburb)} - ${order.delivery_date}`;
    identity.append(name, location);
    const context = document.createElement("span");
    context.className = "workspace-generation-preview-context";
    context.textContent = [
      order.trip_no === "trip2" ? "Trip 2" : "Trip 1",
      `${order.pallet_quantity} pallets`,
      `${order.loose_bags_quantity} bags`,
      `${order.carton_quantity} cartons`,
    ].join(" - ");
    row.append(identity, context);
    list.append(row);
  });
  preview.append(list);
  body.append(preview);
  if (confirmation.error) {
    body.append(createStatus(confirmation.error, "error"));
  }
  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-generation-confirmation-actions";
  actionsRow.append(
    createActionButton("Cancel", actions.closeDeliveryGenerationConfirmation, {
      disabled: isGenerating,
    }),
    createActionButton(
      isGenerating ? "Generating Run Sheet..." : "Confirm Generate Run Sheet",
      actions.confirmGenerateDeliveryRunSheet,
      { disabled: isGenerating, primary: true },
    ),
  );
  body.append(actionsRow);
  return modal;
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
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  });
  select.value = value || "";
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


function createWorkspaceModal(titleText, onClose, {
  eyebrow = "Order Delivery",
  subtitle = "",
  iconName = "document",
  width = "order",
  closeDisabled = false,
} = {}) {
  const root = document.createElement("div");
  root.className = "workspace-modal-backdrop";
  const previouslyFocused = typeof document !== "undefined" ? document.activeElement : null;
  const requestClose = () => {
    onClose();
    if (
      previouslyFocused
      && typeof previouslyFocused.focus === "function"
      && typeof window !== "undefined"
      && typeof window.requestAnimationFrame === "function"
    ) {
      window.requestAnimationFrame(() => {
        if (!document.body.contains(root) && document.body.contains(previouslyFocused)) {
          previouslyFocused.focus();
        }
      });
    }
  };
  const modal = document.createElement("article");
  modal.className = `workspace-modal workspace-modal-${width}`;
  modal.tabIndex = -1;
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-label", titleText);
  modal.addEventListener("click", (event) => event.stopPropagation());
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !closeDisabled) {
      event.preventDefault();
      requestClose();
    }
    if (event.key === "Tab") {
      trapModalFocus(modal, event);
    }
  });
  const header = document.createElement("header");
  header.className = "workspace-modal-header";
  const titleGroup = document.createElement("div");
  titleGroup.className = "workspace-modal-title-group";
  const icon = document.createElement("span");
  icon.className = "workspace-modal-icon";
  icon.append(createIcon(iconName));
  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "workspace-modal-eyebrow";
  kicker.textContent = eyebrow;
  const title = document.createElement("h3");
  title.textContent = titleText;
  copy.append(kicker, title);
  if (subtitle) {
    const description = document.createElement("p");
    description.className = "workspace-modal-subtitle";
    description.textContent = subtitle;
    copy.append(description);
  }
  titleGroup.append(icon, copy);
  const close = createActionButton("Close", requestClose, {
    iconName: "x",
    className: "workspace-modal-close",
    iconOnly: true,
    accessibleLabel: "Close",
  });
  close.disabled = closeDisabled;
  header.append(titleGroup, close);
  const body = document.createElement("div");
  body.className = "workspace-modal-body";
  modal.append(header, body);
  root.append(modal);
  if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
    window.setTimeout(() => modal.focus(), 0);
  }
  return root;
}


function trapModalFocus(modal, event) {
  const focusable = Array.from(
    modal.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"),
  );
  if (!focusable.length) {
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}


function createModalFactSection(titleText, facts) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section";
  section.append(createSectionHeading(titleText, ""));
  const list = document.createElement("dl");
  list.className = "workspace-fact-grid workspace-modal-fact-grid";
  facts.forEach(([labelText, value]) => appendFact(list, labelText, value));
  section.append(list);
  return section;
}


function createFormSection(titleText, children) {
  const section = document.createElement("section");
  section.className = "workspace-form-section";
  const title = document.createElement("h4");
  title.textContent = titleText;
  const grid = document.createElement("div");
  grid.className = "workspace-form-grid";
  children.forEach((child) => grid.append(child));
  section.append(title, grid);
  return section;
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


function createTableHeader(labels) {
  const thead = document.createElement("thead");
  const row = document.createElement("tr");
  labels.forEach((labelText) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = labelText;
    row.append(cell);
  });
  thead.append(row);
  return thead;
}


function createSpecActionGroup(...buttons) {
  const group = document.createElement("div");
  group.className = "workspace-spec-action-group";
  buttons.forEach((button) => group.append(button));
  return group;
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
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  });
  select.value = value || "";
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


function createActionButton(label, onClick, {
  disabled = false,
  primary = false,
  iconName = "",
  className = "",
  iconOnly = false,
  accessibleLabel = "",
} = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = primary ? "button-primary workspace-action-button" : "button-secondary workspace-action-button";
  if (className) {
    button.className = `${button.className} ${className}`;
  }
  button.disabled = disabled;
  if (iconName) {
    button.append(createIcon(iconName));
  }
  if (iconOnly) {
    const description = accessibleLabel || label;
    button.setAttribute("aria-label", description);
    button.title = description;
  } else {
    button.append(document.createTextNode(label));
  }
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick(event);
  });
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
  const products = document.createElement("section");
  products.className = "workspace-modal-section workspace-product-lines";
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
  products.append(createSectionHeading("Product Lines", ""), list);
  return products;
}


function createBadge(label, modifier = "") {
  const badge = document.createElement("span");
  badge.className = `workspace-badge${modifier ? ` workspace-badge-${modifier}` : ""}`;
  badge.textContent = label;
  return badge;
}


function createChip(label) {
  const chip = document.createElement("span");
  chip.className = "workspace-chip";
  chip.textContent = label;
  return chip;
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
