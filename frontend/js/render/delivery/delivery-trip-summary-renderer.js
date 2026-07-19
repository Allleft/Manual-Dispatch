import { formatOptional } from "../../utils/format-utils.js";

import {
  formatDeliveryVehicleConflictMessage,
  formatDeliveryVehicleOptionLabel,
  getDeliveryVehicleConflictDriverNames,
} from "../../utils/delivery-vehicle-utils.js";

import { createDeliveryGenerationCandidate } from "./delivery-generation-modal-renderer.js";

import {
  assignedOrdersForDriver,
  findRunSheetForDriver,
  findVehicleAssignment,
  orderTotals,
  scopedDeliveryDate,
  createSelect,
  createActionButton,
  createMetricGrid,
  createSectionHeading,
  appendFact,
  createBadge,
  createStatus,
  createEmptyState,
  formatLoad,
  isBusy,
} from "./delivery-renderer-utils.js";

export function createDeliveryTripSummary(board, state, actions) {
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

export function createTripSummaryToolbar(deliveryDate, state, actions) {
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

export function createDriverTripSummaryCard(driver, board, deliveryDate, state, actions) {
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
  const runSheet = findRunSheetForDriver(
    state.deliveryTripSummaryRunSheets,
    deliveryDate,
    driver.driver_id,
  );
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

export function createDriverVehicleControl(driver, board, deliveryDate, isLocked, state, actions) {
  const section = document.createElement("div");
  section.className = "workspace-context-row workspace-vehicle-control";
  const currentAssignment = findVehicleAssignment(
    board,
    deliveryDate,
    driver.driver_id,
  );
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

export function createTripPanel(tripNo, driver, board, deliveryDate, isLocked, state, actions) {
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

export function createAssignedOrderRow(order, assignment, driver, isLocked, state, actions) {
  const row = document.createElement("article");
  row.className = "workspace-record-card workspace-order-row-card";
  const title = document.createElement("button");
  title.type = "button";
  title.className = "workspace-order-detail-trigger";
  title.dataset.orderId = order.order_id || "";
  title.setAttribute(
    "aria-label",
    `View Delivery Order ${formatOptional(order.invoice_number, order.order_id)} details`,
  );
  title.addEventListener("click", () => actions.openDeliveryOrderDetail(
    order.order_id,
    { readOnly: true },
  ));
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
