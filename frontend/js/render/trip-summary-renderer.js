import { state } from "../state/app-state.js";
import {
  calculateDriverTotals,
  calculateTripTotals,
  getAssignedOpShopPickupsForDriver,
  getAssignedOrdersForDriver,
  getAssignedTaskForAssignment,
  getAssignmentsForDriver,
  getDriverExceptions,
  getFinalSummaryKey,
  getOrderAssignmentsForDriverTrip,
  getSelectedVehicleForDriver,
  isDriverDeliveryDateFinalized,
  isVehicleSelectedByAnotherDriver,
} from "../state/selectors.js";
import {
  createBadge,
  createHint,
  createOption,
} from "../utils/dom-utils.js";
import {
  formatOptional,
  formatOrderLoadQuantity,
} from "../utils/format-utils.js";

export function renderDriverSummary({
  onDeliveryDateChange,
  onVehicleChange,
  onGenerateDriverSummary,
  onOpenOpShopPickupDetail,
  onOpenOrderDetail,
  onUnassign,
}) {
  renderDriverSummaryDeliveryDateControl({ onDeliveryDateChange });

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
    const assignedOpShopPickups = getAssignedOpShopPickupsForDriver(driver.driver_id);
    const hasAssignedTasks = assignedOrders.length > 0 || assignedOpShopPickups.length > 0;
    const finalSummary = state.finalTripSummaries[getFinalSummaryKey(driver.driver_id)];
    const hasLockedFinalSummary = Boolean(finalSummary);
    const hasUnsavedLockedFinalSummary = Boolean(finalSummary && !finalSummary.summary_id);
    const hasSavedFinalSummary = isDriverDeliveryDateFinalized(driver.driver_id);
    const driverTotals = calculateDriverTotals(driver.driver_id);
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
    vehicleSelect.disabled = state.isSaving || state.isLoading || hasSavedFinalSummary;
    vehicleSelect.append(createOption("", "Select Vehicle", !selectedVehicle));
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
    finalLockHint.textContent = hasSavedFinalSummary
      ? "Final Trip Summary has been saved for this driver and delivery date."
      : hasUnsavedLockedFinalSummary
        ? "Final Trip Summary for this driver is already generated and locked."
        : "";

    const generateButton = document.createElement("button");
    generateButton.type = "button";
    generateButton.className = "button-secondary generate-summary-button";
    generateButton.textContent = state.isSaving ? "Generating..." : "Generate";
    generateButton.disabled = state.isSaving || state.isLoading;
    generateButton.addEventListener("click", () => {
      onGenerateDriverSummary(driver.driver_id);
    });

    vehicleSelect.addEventListener("change", () => {
      onVehicleChange(driver.driver_id, vehicleSelect.value);
    });

    vehicleWrap.append(vehicleSelect);
    header.append(name, driverBadges, loadSummary, vehicleWrap, vehicleStatus, vehicleCapacity);
    if (duplicateHint.textContent) {
      header.append(duplicateHint);
    }
    if (exceptions.length > 0) {
      header.append(exceptionList);
    }
    if (hasAssignedTasks && !hasLockedFinalSummary && !hasSavedFinalSummary) {
      header.append(generateButton);
    }
    if (assignedOpShopPickups.length > 0) {
      const opShopExportHint = document.createElement("p");
      opShopExportHint.className = "vehicle-hint";
      opShopExportHint.textContent =
        "OP SHOP PICKUP tasks appear in a separate Final Trip Summary section and do not affect Delivery totals or trip rows.";
      header.append(opShopExportHint);
    }
    if (finalLockHint.textContent) {
      header.append(finalLockHint);
    }

    const trips = document.createElement("div");
    trips.className = "trip-columns";
    if (!hasAssignedTasks && !hasSavedFinalSummary) {
      const emptyState = document.createElement("p");
      emptyState.className = "empty-trip editable-empty-state";
      emptyState.textContent = hasUnsavedLockedFinalSummary
        ? "No editable tasks. Locked Final Trip Summary is shown below."
        : "No assigned orders for this delivery date.";
      trips.append(emptyState);
    } else {
      ["trip1", "trip2"].forEach((tripNo) => {
        if (getOrderAssignmentsForDriverTrip(driver.driver_id, tripNo).length > 0) {
          trips.append(
            createTripGroup(
              driver.driver_id,
              tripNo,
              tripNo === "trip1" ? "Trip 1" : "Trip 2",
              { onOpenOpShopPickupDetail, onOpenOrderDetail, onUnassign },
            ),
          );
        }
      });
      if (assignedOpShopPickups.length > 0) {
        trips.append(
          createOpShopPickupGroup(driver.driver_id, assignedOpShopPickups, {
            onOpenOpShopPickupDetail,
            onUnassign,
          }),
        );
      }
    }

    card.append(header, trips);
    driverSummaryList.append(card);
  });
}

function renderDriverSummaryDeliveryDateControl({ onDeliveryDateChange }) {
  const deliveryDateInput = document.querySelector("#driver-summary-delivery-date");
  if (!deliveryDateInput) {
    return;
  }

  deliveryDateInput.value = state.driverSummaryDeliveryDate || "";
  deliveryDateInput.disabled = state.isLoading || state.isSaving;
  deliveryDateInput.onchange = () => {
    onDeliveryDateChange(deliveryDateInput.value);
  };
}

function createTripGroup(driverId, tripNo, title, handlers) {
  const group = document.createElement("section");
  group.className = "trip-group";

  const heading = document.createElement("h4");
  heading.textContent = title;

  const tripTotals = calculateTripTotals(driverId, tripNo);
  const tripSummary = document.createElement("p");
  tripSummary.className = "trip-summary";
  tripSummary.textContent = `Pallets: ${tripTotals.pallets} | Loose bags: ${tripTotals.looseBags}`;

  const assignedTasks = getOrderAssignmentsForDriverTrip(driverId, tripNo);

  const taskList = document.createElement("div");
  taskList.className = "assigned-task-list";

  if (assignedTasks.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-trip";
    emptyState.textContent = "No tasks assigned to this trip.";
    taskList.append(emptyState);
  } else {
    assignedTasks.forEach((assignment) => {
      const assignedTask = getAssignedTaskForAssignment(assignment);
      if (!assignedTask) {
        return;
      }

      taskList.append(createAssignedTask(assignment, assignedTask.task, handlers));
    });
  }

  group.append(heading, tripSummary, taskList);
  return group;
}

function createOpShopPickupGroup(driverId, assignedOpShopPickups, handlers) {
  const group = document.createElement("section");
  group.className = "trip-group assigned-opshop-pickups-section";

  const heading = document.createElement("h4");
  heading.textContent = "OP SHOP PICKUPS";

  const summary = document.createElement("p");
  summary.className = "trip-summary";
  summary.textContent = `Pickup tasks: ${assignedOpShopPickups.length}`;

  const taskList = document.createElement("div");
  taskList.className = "assigned-task-list";

  getAssignmentsForDriver(driverId)
    .filter((assignment) => assignment.task_type === "OPSHOP_PICKUP")
    .forEach((assignment) => {
      const pickup = assignedOpShopPickups.find(
        (item) => item.pickup_task_id === assignment.task_id,
      );
      if (pickup) {
        taskList.append(createAssignedOpShopPickupTask(assignment, pickup, handlers));
      }
    });

  group.append(heading, summary, taskList);
  return group;
}

function createAssignedTask(assignment, order, { onOpenOrderDetail, onUnassign }) {
  const row = document.createElement("article");
  row.className = "assigned-task";
  row.tabIndex = 0;
  row.setAttribute("role", "button");
  row.setAttribute("title", "View order details");
  row.setAttribute(
    "aria-label",
    `View details for ${order.invoice_number || order.order_id}, ${order.suburb}, ${formatOrderLoadQuantity(order)}`,
  );
  row.addEventListener("click", () => onOpenOrderDetail(order.order_id));
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenOrderDetail(order.order_id);
    }
  });

  const details = document.createElement("div");

  const suburb = document.createElement("p");
  suburb.className = "assigned-suburb";
  suburb.textContent = order.suburb;

  const pallet = document.createElement("p");
  pallet.className = "assigned-pallet";
  pallet.textContent = `Load: ${formatOrderLoadQuantity(order)}`;

  const deliveryDate = document.createElement("p");
  deliveryDate.className = "assigned-delivery-date";
  deliveryDate.textContent = `Delivery Date: ${order.delivery_date || "-"}`;

  details.append(suburb, deliveryDate, pallet);

  const unassignButton = document.createElement("button");
  unassignButton.type = "button";
  unassignButton.className = "button-secondary";
  unassignButton.disabled = state.isSaving || state.isLoading;
  unassignButton.textContent = state.isSaving ? "Saving..." : "Unassign";
  unassignButton.addEventListener("click", (event) => {
    event.stopPropagation();
    onUnassign(assignment.task_type, assignment.task_id);
  });

  row.append(details, unassignButton);
  return row;
}

function createAssignedOpShopPickupTask(
  assignment,
  pickup,
  { onOpenOpShopPickupDetail, onUnassign },
) {
  const row = document.createElement("article");
  row.className = "assigned-task assigned-opshop-task";
  row.tabIndex = 0;
  row.setAttribute("role", "button");
  row.setAttribute("title", "View OP SHOP PICKUP details");
  row.setAttribute(
    "aria-label",
    `View OP SHOP PICKUP details for ${pickup.opshop_name || pickup.pickup_task_id}`,
  );
  row.addEventListener("click", () => onOpenOpShopPickupDetail(pickup.pickup_task_id));
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenOpShopPickupDetail(pickup.pickup_task_id);
    }
  });

  const details = document.createElement("div");

  const badgeRow = document.createElement("div");
  badgeRow.className = "hint-badge-row";
  badgeRow.append(createBadge("OP SHOP PICKUP", "good"));

  const name = document.createElement("p");
  name.className = "assigned-opshop-name";
  name.textContent = formatOptional(pickup.opshop_name || pickup.pickup_task_id);

  const suburb = document.createElement("p");
  suburb.className = "assigned-opshop-suburb";
  suburb.textContent = formatOptional(pickup.suburb);

  details.append(badgeRow, name, suburb);

  const unassignButton = document.createElement("button");
  unassignButton.type = "button";
  unassignButton.className = "button-secondary";
  unassignButton.disabled = state.isSaving || state.isLoading;
  unassignButton.textContent = state.isSaving ? "Saving..." : "Unassign";
  unassignButton.addEventListener("click", (event) => {
    event.stopPropagation();
    onUnassign(assignment.task_type, assignment.task_id);
  });

  row.append(details, unassignButton);
  return row;
}
