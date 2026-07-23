import {
  formatOptional,
  formatProductDetailLine,
} from "../../utils/format-utils.js";

import {
  findVehicleAssignment,
  orderTotals,
  createWorkspaceModal,
  createModalFactSection,
  createActionButton,
  createSectionHeading,
  createStatus,
  isBusy,
} from "./delivery-renderer-utils.js";

export function createDeliveryGenerationCandidate(
  driver,
  board,
  deliveryDate,
  driverOrders,
  state,
) {
  const vehicleAssignment = findVehicleAssignment(
    board,
    deliveryDate,
    driver.driver_id,
  );
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
    delivery_address: order.delivery_address,
    delivery_date: order.delivery_date,
    note: order.note,
    product_lines: order.product_lines || [],
    trip_no: assignment.trip_no === "trip2" ? "trip2" : "trip1",
    pallet_quantity: Number(order.pallet_quantity || 0),
    loose_bags_quantity: Number(order.loose_bags_quantity || 0),
    carton_quantity: Number(order.carton_quantity || 0),
  }));
  return {
    dispatch_date: board.dispatch_date || deliveryDate,
    delivery_date: deliveryDate,
    driver_id: driver.driver_id,
    driver_name: formatOptional(driver.name, driver.driver_id),
    vehicle: vehicle
      ? { rego: vehicle.rego, pallet_capacity: vehicle.pallet_capacity }
      : null,
    orders,
    totals: {
      ...totals,
      trip1: orders.filter((order) => order.trip_no === "trip1").length,
      trip2: orders.filter((order) => order.trip_no === "trip2").length,
    },
  };
}

export function createDeliveryGenerationConfirmationModal(state, actions) {
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
    const address = document.createElement("span");
    address.textContent = "Address: " + formatOptional(order.delivery_address);
    const products = document.createElement("span");
    products.textContent = "Products: " + ((order.product_lines || [])
      .map((line, index) => formatProductDetailLine(line, index + 1))
      .join("; ") || "No product lines");
    identity.append(name, location, address, products);
    if (order.note) {
      const note = document.createElement("span");
      note.textContent = "Note: " + order.note;
      identity.append(note);
    }
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
