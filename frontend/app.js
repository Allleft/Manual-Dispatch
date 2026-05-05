const demoOrders = [
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
];

const demoDrivers = [
  { driver_id: "DRV-001", name: "John" },
  { driver_id: "DRV-002", name: "Tony" },
  { driver_id: "DRV-003", name: "David" },
];

const demoVehicles = [
  { vehicle_id: "VEH-001", rego: "ABC123" },
  { vehicle_id: "VEH-002", rego: "XYZ888" },
  { vehicle_id: "VEH-003", rego: "MCC001" },
];

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

function renderTaskPool() {
  const taskPoolList = document.querySelector("#task-pool-list");
  taskPoolList.innerHTML = "";

  demoOrders.forEach((order, index) => {
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
    driverSelect.append(createOption("", "Select driver", index === 0));
    demoDrivers.forEach((driver) => {
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
    assignButton.title = "Assign behavior starts in Phase 3";

    controls.append(driverLabel, driverSelect, tripLabel, tripSelect, assignButton);
    card.append(suburb, pallet, controls);
    taskPoolList.append(card);
  });
}

function renderDriverSummary() {
  const driverSummaryList = document.querySelector("#driver-summary-list");
  driverSummaryList.innerHTML = "";

  demoDrivers.forEach((driver) => {
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
    demoVehicles.forEach((vehicle) => {
      vehicleSelect.append(createOption(vehicle.vehicle_id, vehicle.rego));
    });

    vehicleWrap.append(vehicleSelect);
    header.append(name, vehicleWrap);

    const trips = document.createElement("div");
    trips.className = "trip-columns";
    trips.append(createTripGroup("Trip 1", "Static placeholder for trip1 orders"));
    trips.append(createTripGroup("Trip 2", "Static placeholder for trip2 orders"));

    card.append(header, trips);
    driverSummaryList.append(card);
  });
}

function createTripGroup(title, placeholder) {
  const group = document.createElement("section");
  group.className = "trip-group";

  const heading = document.createElement("h4");
  heading.textContent = title;

  const emptyState = document.createElement("p");
  emptyState.className = "empty-trip";
  emptyState.textContent = placeholder;

  group.append(heading, emptyState);
  return group;
}

renderTaskPool();
renderDriverSummary();
