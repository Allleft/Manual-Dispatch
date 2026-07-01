import { state } from "./app-state.js";
import {
  getDisplayPalletQuantity,
  getLooseBagsQuantity,
  getUrgencyLabel,
  normalizeSearchText,
} from "../utils/format-utils.js";

export function getAssignmentForOrder(order) {
  return state.assignments.find(
    (assignment) => assignment.task_type === "ORDER" && assignment.task_id === order.order_id,
  );
}

export function getTaskKey(taskType, taskId) {
  return `${taskType}:${taskId}`;
}

export function isGeneratedTask(taskType, taskId) {
  return state.generatedTaskKeys.has(getTaskKey(taskType, taskId));
}

export function getUnassignedOrders() {
  return state.orders.filter(
    (order) => !getAssignmentForOrder(order) && !isGeneratedTask("ORDER", order.order_id),
  );
}

export function orderMatchesSearch(order, searchText) {
  if (!searchText) {
    return true;
  }

  return [
    order.invoice_number,
    order.order_no,
    order.company_name,
    order.suburb,
    order.postcode,
    order.note,
  ].some((value) => normalizeSearchText(value).includes(searchText));
}

export function orderMatchesUrgencyFilter(order) {
  if (state.urgencyFilter === "All") {
    return true;
  }

  return getUrgencyLabel(order) === state.urgencyFilter;
}

export function orderMatchesTaskPoolDeliveryDateFilter(order) {
  if (!state.taskPoolDeliveryDateFilter) {
    return true;
  }

  return order.delivery_date === state.taskPoolDeliveryDateFilter;
}

export function getFilteredUnassignedOrders() {
  const searchText = normalizeSearchText(state.taskPoolSearch);
  return getUnassignedOrders().filter(
    (order) =>
      orderMatchesSearch(order, searchText) &&
      orderMatchesUrgencyFilter(order) &&
      orderMatchesTaskPoolDeliveryDateFilter(order),
  );
}

export function getOrderByTaskId(taskId) {
  return state.orders.find((order) => order.order_id === taskId);
}

export function getOpShopPickupByTaskId(taskId) {
  return (
    state.opshopBoard?.opshop_pickups?.find(
      (pickup) => pickup.pickup_task_id === taskId,
    ) ||
    state.scheduledOpShopPickups.find((pickup) => pickup.pickup_task_id === taskId) ||
    state.oncallOpShopPickups.find((pickup) => pickup.pickup_task_id === taskId) ||
    state.countrysideOpShopPickups.find((pickup) => pickup.pickup_task_id === taskId) ||
    state.opshopPickups.find((pickup) => pickup.pickup_task_id === taskId) ||
    state.assignedOpShopPickups.find((pickup) => pickup.pickup_task_id === taskId)
  );
}

export function getCountrysideOpShopPickupByTaskId(taskId) {
  return state.countrysideOpShopPickups.find(
    (pickup) => pickup.pickup_task_id === taskId,
  );
}

export function getCountrysideRouteGroupById(routeGroupId) {
  return state.countrysideRouteGroups.find(
    (routeGroup) => routeGroup.route_group_id === routeGroupId,
  );
}

export function getCountrysideRouteGroupNameById(routeGroupId) {
  const routeGroup = getCountrysideRouteGroupById(routeGroupId);
  return routeGroup ? routeGroup.route_group_name : "";
}

export function getCountrysideScheduleCandidatesForRouteGroup(routeGroupId) {
  return state.countrysideOpShopPickupScheduleCandidates.filter(
    (candidate) => !routeGroupId || candidate.route_group_id === routeGroupId,
  );
}

export function findDriverById(driverId) {
  return state.drivers.find((driver) => driver.driver_id === driverId);
}

export function findVehicleById(vehicleId) {
  return state.vehicles.find((vehicle) => vehicle.vehicle_id === vehicleId);
}

export function getDriverVehicleAssignment(driverId) {
  return state.driverVehicleAssignments.find(
    (assignment) =>
      assignment.driver_id === driverId &&
      assignment.dispatch_date === state.dispatchDate &&
      assignment.delivery_date === state.driverSummaryDeliveryDate,
  );
}

export function getSelectedVehicleForDriver(driverId) {
  const assignment = getDriverVehicleAssignment(driverId);
  return assignment ? findVehicleById(assignment.vehicle_id) : null;
}

export function isVehicleSelectedByAnotherDriver(driverId, vehicleId) {
  if (!vehicleId) {
    return false;
  }

  return state.driverVehicleAssignments.some(
    (assignment) =>
      assignment.dispatch_date === state.dispatchDate &&
      assignment.delivery_date === state.driverSummaryDeliveryDate &&
      assignment.vehicle_id === vehicleId &&
      assignment.driver_id !== driverId,
  );
}

export function getOrderPreferredDriverName(order) {
  const driver = order.preferred_driver_id ? findDriverById(order.preferred_driver_id) : null;
  return driver ? driver.name : "";
}

export function getAssignedOrdersForDriver(driverId) {
  return getAssignmentsForDriver(driverId)
    .map((assignment) => getOrderByTaskId(assignment.task_id))
    .filter(Boolean);
}

export function getAssignedOrdersForTrip(driverId, tripNo) {
  return getAssignmentsForDriverTrip(driverId, tripNo)
    .map((assignment) => getOrderByTaskId(assignment.task_id))
    .filter(Boolean);
}

export function getOrderAssignmentsForDriverTrip(driverId, tripNo) {
  return getAssignmentsForDriverTrip(driverId, tripNo).filter(
    (assignment) => assignment.task_type === "ORDER",
  );
}

export function getAssignedOpShopPickupsForDriver(driverId) {
  return getAssignmentsForDriver(driverId)
    .filter((assignment) => assignment.task_type === "OPSHOP_PICKUP")
    .map((assignment) => getOpShopPickupByTaskId(assignment.task_id))
    .filter(
      (pickup) =>
        pickup && !isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id),
    );
}

export function getAssignedTaskForAssignment(assignment) {
  if (assignment.task_type === "ORDER") {
    const order = getOrderByTaskId(assignment.task_id);
    return order ? { assignment, task: order, taskType: "ORDER" } : null;
  }
  if (assignment.task_type === "OPSHOP_PICKUP") {
    const pickup = getOpShopPickupByTaskId(assignment.task_id);
    return pickup ? { assignment, task: pickup, taskType: "OPSHOP_PICKUP" } : null;
  }
  return null;
}

export function getAssignmentsForDriver(driverId) {
  return state.assignments.filter(
    (assignment) =>
      assignment.driver_id === driverId &&
      (!assignment.dispatch_date || assignment.dispatch_date === state.dispatchDate) &&
      assignmentMatchesDriverSummaryDeliveryDate(assignment),
  );
}

export function getAssignmentsForDriverTrip(driverId, tripNo) {
  return getAssignmentsForDriver(driverId).filter((assignment) => assignment.trip_no === tripNo);
}

export function calculateTotals(orders) {
  return orders.reduce(
    (totals, order) => ({
      pallets: totals.pallets + getDisplayPalletQuantity(order),
      looseBags: totals.looseBags + getLooseBagsQuantity(order),
    }),
    { pallets: 0, looseBags: 0 },
  );
}

export function calculateDriverTotals(driverId) {
  return calculateTotals(getAssignedOrdersForDriver(driverId));
}

export function calculateTripTotals(driverId, tripNo) {
  return calculateTotals(getAssignedOrdersForTrip(driverId, tripNo));
}

export function getTripCapacityExceptions(driverId) {
  const selectedVehicle = getSelectedVehicleForDriver(driverId);
  if (!selectedVehicle) {
    return [];
  }

  const capacity = Number(selectedVehicle.pallet_capacity || 0);
  if (!Number.isFinite(capacity) || capacity <= 0) {
    return [];
  }

  return ["trip1", "trip2"]
    .map((tripNo) => {
      const totals = calculateTripTotals(driverId, tripNo);
      return {
        tripNo,
        pallets: totals.pallets,
        exceeds: totals.pallets > capacity,
      };
    })
    .filter((item) => item.exceeds);
}

export function getDriverExceptions(driver) {
  const messages = [];
  const assignedOrders = getAssignedOrdersForDriver(driver.driver_id);

  if (driver.pallet_only && assignedOrders.some((order) => getLooseBagsQuantity(order) > 0)) {
    messages.push("Exception: Driver only handles pallet orders");
  }

  getTripCapacityExceptions(driver.driver_id).forEach((item) => {
    const tripLabel = item.tripNo === "trip1" ? "Trip 1" : "Trip 2";
    messages.push(`Exception: ${tripLabel} pallets exceed selected vehicle capacity`);
  });

  return messages;
}

export function getFinalSummaryKey(driverId, deliveryDate = state.driverSummaryDeliveryDate) {
  return `${driverId}:${deliveryDate || ""}`;
}

export function isDriverDeliveryDateFinalized(driverId, deliveryDate = state.driverSummaryDeliveryDate) {
  return state.finalizedDriverDeliveryDates.some(
    (lockedDate) =>
      lockedDate.driver_id === driverId &&
      lockedDate.delivery_date === deliveryDate,
  );
}

function assignmentMatchesDriverSummaryDeliveryDate(assignment) {
  if (!state.driverSummaryDeliveryDate) {
    return false;
  }

  if (assignment.task_type === "OPSHOP_PICKUP") {
    const pickup = getOpShopPickupByTaskId(assignment.task_id);
    return Boolean(pickup && pickup.pickup_date === state.driverSummaryDeliveryDate);
  }

  const order = getOrderByTaskId(assignment.task_id);
  return Boolean(order && order.delivery_date === state.driverSummaryDeliveryDate);
}
