const state = {
  orders: [
    {
      order_id: "ORD-001",
      suburb: "Dandenong",
      pallet_quantity: 2,
      loose_bags_quantity: 0,
    },
    {
      order_id: "ORD-002",
      suburb: "Clayton",
      pallet_quantity: 0,
      loose_bags_quantity: 12,
    },
    {
      order_id: "ORD-003",
      suburb: "Springvale",
      pallet_quantity: 3,
      loose_bags_quantity: 0,
    },
  ],
  drivers: [
    { driver_id: "DRV-001", name: "John" },
    { driver_id: "DRV-002", name: "Tony" },
    { driver_id: "DRV-003", name: "David" },
  ],
  vehicles: [
    { vehicle_id: "VEH-001", rego: "ABC123" },
    { vehicle_id: "VEH-002", rego: "XYZ888" },
    { vehicle_id: "VEH-003", rego: "MCC001" },
  ],
  assignments: [],
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

function createOption(value, label, selected = false) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  option.selected = selected;
  return option;
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

    const suburb = document.createElement("h3");
    suburb.id = `order-${order.order_id}`;
    suburb.textContent = order.suburb;

    const pallet = document.createElement("p");
    pallet.className = "metric-pill";
    pallet.textContent = `Pallet: ${getDisplayPalletQuantity(order)}`;

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

    driverSelect.addEventListener("change", () => {
      assignButton.disabled = driverSelect.value === "";
      assignButton.title = driverSelect.value
        ? "Assign this Order to the selected Driver and Trip"
        : "Select a driver to enable Assign";
    });

    assignButton.addEventListener("click", () => {
      assignOrder(order.order_id, driverSelect.value, tripSelect.value);
    });

    controls.append(driverLabel, driverSelect, tripLabel, tripSelect, assignButton);
    card.append(suburb, pallet, controls);
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

    const vehicleWrap = document.createElement("label");
    vehicleWrap.className = "vehicle-select";
    vehicleWrap.textContent = "Choose Vehicle";

    const vehicleSelect = document.createElement("select");
    vehicleSelect.append(createOption("", "Select rego", true));
    state.vehicles.forEach((vehicle) => {
      vehicleSelect.append(createOption(vehicle.vehicle_id, vehicle.rego));
    });

    vehicleWrap.append(vehicleSelect);
    header.append(name, vehicleWrap);

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

  group.append(heading, taskList);
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
  pallet.textContent = `Pallet: ${getDisplayPalletQuantity(order)}`;

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
