import { DEFAULT_DISPATCH_DATE, state } from "../state/app-state.js";
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
import { createIcon } from "../utils/icon-utils.js";

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
    const driverIcon = document.createElement("span");
    driverIcon.className = "driver-card-name-icon";
    driverIcon.setAttribute("aria-hidden", "true");
    driverIcon.append(createIcon("user"));
    name.append(driverIcon, document.createTextNode(driver.name));

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
    const hasUnsavedLockedFinalSummary = Boolean(
      finalSummary && finalSummary.status !== "SAVED",
    );
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
    vehicleSelect.disabled =
      state.isSaving || state.isLoading || hasLockedFinalSummary || hasSavedFinalSummary;
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
    header.append(name, driverBadges);
    if (finalLockHint.textContent) {
      header.append(finalLockHint);
    }

    const trips = document.createElement("div");
    trips.className = "trip-columns";

    const canGenerate = hasAssignedTasks && !hasLockedFinalSummary && !hasSavedFinalSummary;
    const deliveryGenerateButton = canGenerate && assignedOpShopPickups.length === 0
      ? generateButton
      : null;
    const opshopGenerateButton = canGenerate && assignedOpShopPickups.length > 0
      ? generateButton
      : null;

    trips.append(
      createDeliveryOrdersPanel(driver.driver_id, {
        duplicateHint,
        exceptionList,
        exceptions,
        generateButton: deliveryGenerateButton,
        hasSavedFinalSummary,
        hasUnsavedLockedFinalSummary,
        loadSummary,
        vehicleCapacity,
        vehicleStatus,
        vehicleWrap,
      }, { onOpenOpShopPickupDetail, onOpenOrderDetail, onUnassign }),
    );

    if (assignedOpShopPickups.length > 0) {
      trips.append(
        createOpShopPickupGroup(driver.driver_id, assignedOpShopPickups, {
          onOpenOpShopPickupDetail,
          onUnassign,
        }, {
          generateButton: opshopGenerateButton,
        }),
      );
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

  const minimumDeliveryDate = state.dispatchDate || DEFAULT_DISPATCH_DATE;
  deliveryDateInput.min = minimumDeliveryDate;
  deliveryDateInput.value = state.driverSummaryDeliveryDate || minimumDeliveryDate;
  deliveryDateInput.disabled = state.isLoading || state.isSaving;
  deliveryDateInput.onchange = () => {
    onDeliveryDateChange(deliveryDateInput.value || minimumDeliveryDate);
  };
}

function createDeliveryOrdersPanel(driverId, {
  duplicateHint,
  exceptionList,
  exceptions,
  generateButton,
  hasSavedFinalSummary,
  hasUnsavedLockedFinalSummary,
  loadSummary,
  vehicleCapacity,
  vehicleStatus,
  vehicleWrap,
}, handlers) {
  const panel = document.createElement("section");
  panel.className = "trip-group assigned-delivery-orders-section";

  panel.append(createTripPanelHeader("DELIVERY ORDERS", "box", generateButton));
  panel.append(loadSummary, vehicleWrap, vehicleStatus, vehicleCapacity);

  if (duplicateHint.textContent) {
    panel.append(duplicateHint);
  }
  if (exceptions.length > 0) {
    panel.append(exceptionList);
  }

  const taskList = document.createElement("div");
  taskList.className = "delivery-trip-list";
  const hasOrderTasks = ["trip1", "trip2"].some(
    (tripNo) => getOrderAssignmentsForDriverTrip(driverId, tripNo).length > 0,
  );

  if (!hasOrderTasks && !hasSavedFinalSummary) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-trip editable-empty-state";
    emptyState.textContent = hasUnsavedLockedFinalSummary
      ? "No editable tasks. Locked Final Trip Summary is shown below."
      : "No assigned orders for this delivery date.";
    taskList.append(emptyState);
  } else {
    ["trip1", "trip2"].forEach((tripNo) => {
      if (getOrderAssignmentsForDriverTrip(driverId, tripNo).length > 0) {
        taskList.append(
          createTripGroup(
            driverId,
            tripNo,
            tripNo === "trip1" ? "Trip 1" : "Trip 2",
            handlers,
          ),
        );
      }
    });
  }

  panel.append(taskList);
  return panel;
}

function createTripGroup(driverId, tripNo, title, handlers) {
  const group = document.createElement("section");
  group.className = "trip-group";

  const heading = createTripPanelHeader(title, "box");

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

function createOpShopPickupGroup(driverId, assignedOpShopPickups, handlers, {
  generateButton = null,
} = {}) {
  const group = document.createElement("section");
  group.className = "trip-group assigned-opshop-pickups-section";

  const heading = createTripPanelHeader("OP SHOP PICKUPS", "bag", generateButton);

  const summary = document.createElement("p");
  summary.className = "trip-summary";
  summary.textContent = `Pickup tasks: ${assignedOpShopPickups.length}`;

  const taskList = document.createElement("div");
  taskList.className = "assigned-task-list";

  createOpShopPickupEntries(driverId, assignedOpShopPickups).forEach((entry) => {
    if (entry.type === "route-group") {
      taskList.append(createAssignedCountrysideRouteGroup(entry.group, handlers));
      return;
    }
    taskList.append(createAssignedOpShopPickupTask(entry.assignment, entry.pickup, handlers));
  });

  group.append(heading, summary, taskList);
  return group;
}

function createTripPanelHeader(title, iconName, actionButton = null) {
  const header = document.createElement("div");
  header.className = "trip-group-panel-header";

  const heading = document.createElement("h4");
  heading.append(createTripHeadingIcon(iconName), document.createTextNode(title));
  header.append(heading);

  if (actionButton) {
    header.append(actionButton);
  }

  return header;
}

function createOpShopPickupEntries(driverId, assignedOpShopPickups) {
  const entries = [];
  const routeGroups = new Map();
  getAssignmentsForDriver(driverId)
    .filter((assignment) => assignment.task_type === "OPSHOP_PICKUP")
    .forEach((assignment) => {
      const pickup = assignedOpShopPickups.find((item) => item.pickup_task_id === assignment.task_id);
      if (!pickup) {
        return;
      }
      if (isCountrysideRouteGroupPickup(pickup)) {
        const groupKey = [
          assignment.trip_no || "",
          pickup.route_group_id,
        ].join("|");
        if (!routeGroups.has(groupKey)) {
          const group = {
            assignments: [],
            pickupDate: pickup.pickup_date || "",
            pickups: [],
            routeGroupId: pickup.route_group_id,
            routeGroupName: pickup.route_group_name || pickup.route_group_id,
            tripNo: assignment.trip_no || "",
          };
          routeGroups.set(groupKey, group);
          entries.push({ type: "route-group", group });
        }
        const group = routeGroups.get(groupKey);
        group.assignments.push(assignment);
        group.pickups.push(pickup);
        return;
      }
      entries.push({ type: "pickup", assignment, pickup });
    });
  return entries;
}

function isCountrysideRouteGroupPickup(pickup) {
  return Boolean(
    pickup &&
    pickup.pickup_category === "COUNTRYSIDE" &&
    pickup.route_group_id,
  );
}

function createAssignedCountrysideRouteGroup(
  group,
  handlers,
) {
  const section = document.createElement("section");
  section.className = "assigned-opshop-route-group";

  const header = document.createElement("header");
  header.className = "assigned-opshop-route-group-header";

  const title = document.createElement("h5");
  title.className = "assigned-opshop-route-group-title";
  const routeGroupIcon = document.createElement("span");
  routeGroupIcon.className = "assigned-opshop-route-group-icon";
  routeGroupIcon.setAttribute("aria-hidden", "true");
  routeGroupIcon.append(createIcon("tree"));
  title.append(
    routeGroupIcon,
    document.createTextNode(`Countryside Route Group: ${formatOptional(group.routeGroupName)}`),
  );

  const unassignButton = document.createElement("button");
  unassignButton.type = "button";
  unassignButton.className = "button-secondary";
  unassignButton.disabled =
    state.isSaving ||
    state.isLoading ||
    group.pickups.some((pickup, index) =>
      isDriverDeliveryDateFinalized(group.assignments[index]?.driver_id || "", pickup.pickup_date),
    );
  unassignButton.textContent = state.isSaving ? "Saving..." : "Unassign Route Group";
  unassignButton.addEventListener("click", (event) => {
    event.stopPropagation();
    if (unassignButton.disabled) {
      return;
    }
    handlers.onUnassign(
      "OPSHOP_PICKUP",
      group.assignments.map((assignment) => assignment.task_id),
    );
  });

  header.append(title, unassignButton);

  const cardList = document.createElement("div");
  cardList.className = "assigned-opshop-route-group-card-list";
  group.pickups.forEach((pickup, index) => {
    cardList.append(
      createAssignedOpShopPickupTask(group.assignments[index], pickup, handlers, {
        showUnassignButton: false,
      }),
    );
  });

  section.append(header, cardList);
  return section;
}

function createTripHeadingIcon(name) {
  const icon = document.createElement("span");
  icon.className = "trip-group-heading-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.append(createIcon(name));
  return icon;
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
  { showUnassignButton = true } = {},
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
  if (pickup.pickup_category === "COUNTRYSIDE" || pickup.route_group_name) {
    badgeRow.append(createBadge("Countryside"));
  }

  const name = document.createElement("p");
  name.className = "assigned-opshop-name";
  name.textContent = formatOptional(pickup.opshop_name || pickup.pickup_task_id);

  const suburb = document.createElement("p");
  suburb.className = "assigned-opshop-suburb";
  suburb.textContent = formatOptional(pickup.suburb);

  details.append(badgeRow, name, suburb);

  row.append(details);
  if (showUnassignButton) {
    const unassignButton = document.createElement("button");
    unassignButton.type = "button";
    unassignButton.className = "button-secondary";
    unassignButton.disabled = state.isSaving || state.isLoading;
    unassignButton.textContent = state.isSaving ? "Saving..." : "Unassign";
    unassignButton.addEventListener("click", (event) => {
      event.stopPropagation();
      onUnassign(assignment.task_type, assignment.task_id);
    });
    row.append(unassignButton);
  }
  return row;
}
