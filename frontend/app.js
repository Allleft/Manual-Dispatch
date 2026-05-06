const state = {
  dispatchDate: "2026-05-05",
  orders: [
    {
      order_id: "ORD-001",
      suburb: "Dandenong",
      pallet_quantity: 2,
      loose_bags_quantity: 0,
      zone: "South East",
      urgency: "Urgent",
      preferred_driver_id: "D001",
      start_time: "08:00",
      end_time: "12:00",
      note: "Call before delivery",
    },
    {
      order_id: "ORD-002",
      suburb: "Clayton",
      pallet_quantity: 0,
      loose_bags_quantity: 12,
      zone: "South East",
      urgency: "Normal",
      preferred_driver_id: "D002",
      start_time: "10:00",
      end_time: "14:00",
      note: "Loose bags only",
    },
    {
      order_id: "ORD-003",
      suburb: "Springvale",
      pallet_quantity: 3,
      loose_bags_quantity: 0,
      zone: "South East",
      urgency: "Normal",
      preferred_driver_id: null,
      start_time: "09:00",
      end_time: "15:00",
      note: "",
    },
  ],
  drivers: [
    {
      driver_id: "D001",
      name: "John",
      start_time: "08:00",
      end_time: "16:00",
      is_available: true,
      preferred_zone: "South East",
    },
    {
      driver_id: "D002",
      name: "Tony",
      start_time: "08:00",
      end_time: "16:00",
      is_available: true,
      preferred_zone: "West",
    },
    {
      driver_id: "D003",
      name: "David",
      start_time: "09:00",
      end_time: "15:00",
      is_available: true,
      preferred_zone: "North",
    },
  ],
  vehicles: [
    { vehicle_id: "V001", rego: "ABC123", pallet_capacity: 10 },
    { vehicle_id: "V002", rego: "XYZ888", pallet_capacity: 4 },
    { vehicle_id: "V003", rego: "MCC001", pallet_capacity: 6 },
  ],
  assignments: [],
  driverVehicleAssignments: [],
};

let nextAssignmentNumber = 1;

function getDisplayPalletQuantity(order) {
  const palletQuantity = Number(order.pallet_quantity);
  const looseBagsQuantity = Number(order.loose_bags_quantity);

  if ((!Number.isFinite(palletQuantity) || palletQuantity === 0) && looseBagsQuantity > 0) {
    return 0;
  }

  return Number.isFinite(palletQuantity) ? palletQuantity : 0;
}

function getLooseBagsQuantity(order) {
  const looseBagsQuantity = Number(order.loose_bags_quantity);
  return Number.isFinite(looseBagsQuantity) ? looseBagsQuantity : 0;
}

function createOption(value, label, selected = false) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  option.selected = selected;
  return option;
}

function createBadge(text, variant = "neutral") {
  const badge = document.createElement("span");
  badge.className = `hint-badge hint-badge-${variant}`;
  badge.textContent = text;
  return badge;
}

function createHint(text, variant = "neutral") {
  const hint = document.createElement("p");
  hint.className = `hint-row hint-row-${variant}`;
  hint.textContent = text;
  return hint;
}

function getAssignmentForOrder(order) {
  return state.assignments.find(
    (assignment) =>
      assignment.task_type === "ORDER" && assignment.task_id === order.order_id,
  );
}

function getUnassignedOrders() {
  return state.orders.filter((order) => !getAssignmentForOrder(order));
}

function getOrderByTaskId(taskId) {
  return state.orders.find((order) => order.order_id === taskId);
}

function findDriverById(driverId) {
  return state.drivers.find((driver) => driver.driver_id === driverId);
}

function findVehicleById(vehicleId) {
  return state.vehicles.find((vehicle) => vehicle.vehicle_id === vehicleId);
}

function getDriverVehicleAssignment(driverId) {
  return state.driverVehicleAssignments.find(
    (assignment) =>
      assignment.dispatch_date === state.dispatchDate && assignment.driver_id === driverId,
  );
}

function getSelectedVehicleForDriver(driverId) {
  const assignment = getDriverVehicleAssignment(driverId);
  return assignment ? findVehicleById(assignment.vehicle_id) : null;
}

function upsertDriverVehicleAssignment(driverId, vehicleId) {
  const existingIndex = state.driverVehicleAssignments.findIndex(
    (assignment) =>
      assignment.dispatch_date === state.dispatchDate && assignment.driver_id === driverId,
  );

  if (!vehicleId) {
    if (existingIndex >= 0) {
      state.driverVehicleAssignments.splice(existingIndex, 1);
    }
    return;
  }

  const nextAssignment = {
    dispatch_date: state.dispatchDate,
    driver_id: driverId,
    vehicle_id: vehicleId,
  };

  if (existingIndex >= 0) {
    state.driverVehicleAssignments[existingIndex] = nextAssignment;
  } else {
    state.driverVehicleAssignments.push(nextAssignment);
  }
}

function isVehicleSelectedByAnotherDriver(driverId, vehicleId) {
  if (!vehicleId) {
    return false;
  }

  return state.driverVehicleAssignments.some(
    (assignment) =>
      assignment.dispatch_date === state.dispatchDate &&
      assignment.driver_id !== driverId &&
      assignment.vehicle_id === vehicleId,
  );
}

function getOrderPreferredDriverName(order) {
  const driver = order.preferred_driver_id ? findDriverById(order.preferred_driver_id) : null;
  return driver ? driver.name : "";
}

function isZoneDifferent(order, driver) {
  return Boolean(order.zone && driver && driver.preferred_zone && order.zone !== driver.preferred_zone);
}

function timeToMinutes(timeValue) {
  if (!timeValue) {
    return null;
  }

  const [hours, minutes] = timeValue.split(":").map(Number);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
    return null;
  }

  return hours * 60 + minutes;
}

function isOutsideDriverHours(order, driver) {
  if (!driver) {
    return false;
  }

  const orderStart = timeToMinutes(order.start_time);
  const orderEnd = timeToMinutes(order.end_time);
  const driverStart = timeToMinutes(driver.start_time);
  const driverEnd = timeToMinutes(driver.end_time);

  if ([orderStart, orderEnd, driverStart, driverEnd].some((value) => value === null)) {
    return false;
  }

  return orderStart < driverStart || orderEnd > driverEnd;
}

function getAssignedOrdersForDriver(driverId) {
  return state.assignments
    .filter((assignment) => assignment.driver_id === driverId)
    .map((assignment) => getOrderByTaskId(assignment.task_id))
    .filter(Boolean);
}

function getAssignedOrdersForTrip(driverId, tripNo) {
  return state.assignments
    .filter((assignment) => assignment.driver_id === driverId && assignment.trip_no === tripNo)
    .map((assignment) => getOrderByTaskId(assignment.task_id))
    .filter(Boolean);
}

function calculateTotals(orders) {
  return orders.reduce(
    (totals, order) => ({
      pallets: totals.pallets + getDisplayPalletQuantity(order),
      looseBags: totals.looseBags + getLooseBagsQuantity(order),
    }),
    { pallets: 0, looseBags: 0 },
  );
}

function calculateDriverTotals(driverId) {
  return calculateTotals(getAssignedOrdersForDriver(driverId));
}

function calculateTripTotals(driverId, tripNo) {
  return calculateTotals(getAssignedOrdersForTrip(driverId, tripNo));
}

function isVehicleCapacityExceeded(driverId) {
  const selectedVehicle = getSelectedVehicleForDriver(driverId);
  if (!selectedVehicle) {
    return false;
  }

  return calculateDriverTotals(driverId).pallets > Number(selectedVehicle.pallet_capacity || 0);
}

function createAssignmentId() {
  const assignmentId = `A-${String(nextAssignmentNumber).padStart(3, "0")}`;
  nextAssignmentNumber += 1;
  return assignmentId;
}

function assignOrder(orderId, driverId, tripNo) {
  if (!driverId || getAssignmentForOrder({ order_id: orderId })) {
    return;
  }

  state.assignments.push({
    assignment_id: createAssignmentId(),
    task_type: "ORDER",
    task_id: orderId,
    driver_id: driverId,
    trip_no: tripNo || "trip1",
  });

  renderBoard();
}

function unassignOrder(assignmentId) {
  state.assignments = state.assignments.filter(
    (assignment) => assignment.assignment_id !== assignmentId,
  );

  renderBoard();
}

function renderTaskPool() {
  const taskPoolList = document.querySelector("#task-pool-list");
  taskPoolList.innerHTML = "";

  const unassignedOrders = getUnassignedOrders();

  if (unassignedOrders.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-board";
    emptyState.textContent = "All demo Orders are currently assigned.";
    taskPoolList.append(emptyState);
    return;
  }

  unassignedOrders.forEach((order) => {
    const card = document.createElement("article");
    card.className = "order-card";
    card.setAttribute("aria-labelledby", `order-${order.order_id}`);

    const header = document.createElement("div");
    header.className = "order-card-header";

    const suburb = document.createElement("h3");
    suburb.id = `order-${order.order_id}`;
    suburb.textContent = order.suburb;

    const pallet = document.createElement("p");
    pallet.className = "metric-pill";
    pallet.textContent = `Pallet: ${getDisplayPalletQuantity(order)}`;

    header.append(suburb, pallet);

    const badgeRow = document.createElement("div");
    badgeRow.className = "hint-badge-row";
    badgeRow.append(
      createBadge(order.urgency || "Normal", order.urgency === "Urgent" ? "urgent" : "neutral"),
      createBadge(`Zone: ${order.zone || "Not set"}`),
    );

    const hintList = document.createElement("div");
    hintList.className = "order-hints";
    hintList.append(createHint(`Window: ${order.start_time || "--"}-${order.end_time || "--"}`));

    const preferredDriverName = getOrderPreferredDriverName(order);
    if (preferredDriverName) {
      hintList.append(createHint(`Preferred: ${preferredDriverName}`));
    }

    if (order.note) {
      hintList.append(createHint(`Note: ${order.note}`));
    }

    const controls = document.createElement("div");
    controls.className = "order-controls";

    const driverLabel = document.createElement("label");
    driverLabel.textContent = "Driver";
    driverLabel.setAttribute("for", `driver-${order.order_id}`);

    const driverSelect = document.createElement("select");
    driverSelect.id = `driver-${order.order_id}`;
    driverSelect.append(createOption("", "Select driver", true));
    state.drivers.forEach((driver) => {
      driverSelect.append(createOption(driver.driver_id, driver.name));
    });

    const tripLabel = document.createElement("label");
    tripLabel.textContent = "Trip";
    tripLabel.setAttribute("for", `trip-${order.order_id}`);

    const tripSelect = document.createElement("select");
    tripSelect.id = `trip-${order.order_id}`;
    tripSelect.append(createOption("trip1", "trip1", true));
    tripSelect.append(createOption("trip2", "trip2"));

    const assignButton = document.createElement("button");
    assignButton.type = "button";
    assignButton.disabled = true;
    assignButton.textContent = "Assign";
    assignButton.title = "Select a driver to enable Assign";

    const selectionHints = document.createElement("div");
    selectionHints.className = "selection-hints";

    const renderSelectionHints = () => {
      const selectedDriver = findDriverById(driverSelect.value);
      selectionHints.innerHTML = "";

      if (!selectedDriver) {
        return;
      }

      if (preferredDriverName && selectedDriver.driver_id !== order.preferred_driver_id) {
        selectionHints.append(createHint(`Preferred driver is ${preferredDriverName}`, "warning"));
      }

      if (isZoneDifferent(order, selectedDriver)) {
        selectionHints.append(createHint("Zone differs from driver preference", "warning"));
      }

      if (isOutsideDriverHours(order, selectedDriver)) {
        selectionHints.append(createHint("Outside driver hours", "warning"));
      }
    };

    driverSelect.addEventListener("change", () => {
      assignButton.disabled = driverSelect.value === "";
      assignButton.title = driverSelect.value
        ? "Assign this Order to the selected Driver and Trip"
        : "Select a driver to enable Assign";
      renderSelectionHints();
    });

    assignButton.addEventListener("click", () => {
      assignOrder(order.order_id, driverSelect.value, tripSelect.value);
    });

    controls.append(
      driverLabel,
      driverSelect,
      tripLabel,
      tripSelect,
      selectionHints,
      assignButton,
    );
    card.append(header, badgeRow, hintList, controls);
    taskPoolList.append(card);
  });
}

function renderDriverSummary() {
  const driverSummaryList = document.querySelector("#driver-summary-list");
  driverSummaryList.innerHTML = "";

  state.drivers.forEach((driver) => {
    const card = document.createElement("article");
    card.className = "driver-card";

    const header = document.createElement("div");
    header.className = "driver-card-header";

    const name = document.createElement("h3");
    name.textContent = driver.name;

    const driverBadges = document.createElement("div");
    driverBadges.className = "hint-badge-row";
    driverBadges.append(
      createBadge(driver.is_available ? "Available" : "Not available", driver.is_available ? "good" : "warning"),
      createBadge(`Preferred zone: ${driver.preferred_zone || "Not set"}`),
    );

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
    vehicleSelect.append(createOption("", "Select vehicle", !selectedVehicle));
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

    const capacityWarning = document.createElement("p");
    capacityWarning.className = "vehicle-hint";
    capacityWarning.textContent = isVehicleCapacityExceeded(driver.driver_id)
      ? "Capacity warning: assigned pallets exceed selected vehicle pallet capacity."
      : "";

    vehicleSelect.addEventListener("change", () => {
      upsertDriverVehicleAssignment(driver.driver_id, vehicleSelect.value);
      renderDriverSummary();
    });

    vehicleWrap.append(vehicleSelect);
    header.append(name, driverBadges, loadSummary, vehicleWrap, vehicleStatus, vehicleCapacity);
    if (duplicateHint.textContent) {
      header.append(duplicateHint);
    }
    if (capacityWarning.textContent) {
      header.append(capacityWarning);
    }

    const trips = document.createElement("div");
    trips.className = "trip-columns";
    trips.append(createTripGroup(driver.driver_id, "trip1", "Trip 1"));
    trips.append(createTripGroup(driver.driver_id, "trip2", "Trip 2"));

    card.append(header, trips);
    driverSummaryList.append(card);
  });
}

function createTripGroup(driverId, tripNo, title) {
  const group = document.createElement("section");
  group.className = "trip-group";

  const heading = document.createElement("h4");
  heading.textContent = title;

  const tripTotals = calculateTripTotals(driverId, tripNo);
  const tripSummary = document.createElement("p");
  tripSummary.className = "trip-summary";
  tripSummary.textContent = `Pallets: ${tripTotals.pallets} | Loose bags: ${tripTotals.looseBags}`;

  const assignedTasks = state.assignments.filter(
    (assignment) => assignment.driver_id === driverId && assignment.trip_no === tripNo,
  );

  const taskList = document.createElement("div");
  taskList.className = "assigned-task-list";

  if (assignedTasks.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-trip";
    emptyState.textContent = "No tasks assigned to this trip.";
    taskList.append(emptyState);
  } else {
    assignedTasks.forEach((assignment) => {
      const order = getOrderByTaskId(assignment.task_id);
      if (!order) {
        return;
      }

      taskList.append(createAssignedTask(assignment, order));
    });
  }

  group.append(heading, tripSummary, taskList);
  return group;
}

function createAssignedTask(assignment, order) {
  const row = document.createElement("article");
  row.className = "assigned-task";
  row.setAttribute("aria-label", `${order.suburb}, Pallet ${getDisplayPalletQuantity(order)}`);

  const details = document.createElement("div");

  const suburb = document.createElement("p");
  suburb.className = "assigned-suburb";
  suburb.textContent = order.suburb;

  const pallet = document.createElement("p");
  pallet.className = "assigned-pallet";
  pallet.textContent = `Pallet: ${getDisplayPalletQuantity(order)} | Loose bags: ${getLooseBagsQuantity(order)}`;

  details.append(suburb, pallet);

  const unassignButton = document.createElement("button");
  unassignButton.type = "button";
  unassignButton.className = "button-secondary";
  unassignButton.textContent = "Unassign";
  unassignButton.addEventListener("click", () => {
    unassignOrder(assignment.assignment_id);
  });

  row.append(details, unassignButton);
  return row;
}

function renderBoard() {
  renderTaskPool();
  renderDriverSummary();
}

renderBoard();
