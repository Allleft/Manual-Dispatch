import {
  createBoundInput,
  createBoundCheckbox,
  createWorkspaceModal,
  createTableCell,
  createTableHeader,
  createActionButton,
  createStatus,
  createEmptyState,
} from "./delivery-renderer-utils.js";

export function createDeliverySpecificationModal(state, actions) {
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

export function createDriverSpecificationPanel(state, actions) {
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

export function createVehicleSpecificationPanel(state, actions) {
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

export function createDriverForm(state, actions) {
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

export function createVehicleForm(state, actions) {
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

export function createSpecActionGroup(...buttons) {
  const group = document.createElement("div");
  group.className = "workspace-spec-action-group";
  buttons.forEach((button) => group.append(button));
  return group;
}

export function createSpecAvailability(checked, onChange) {
  return createBoundCheckbox("Available", checked, onChange);
}
