import { state } from "./app-state.js";


export function normalizeBoardResponse(payload) {
  return {
    dispatchDate: payload.dispatch_date || state.dispatchDate,
    orders: payload.orders || [],
    drivers: payload.drivers || [],
    vehicles: payload.vehicles || [],
    assignments: payload.assignments || [],
    finalizedDriverDeliveryDates: payload.finalized_driver_delivery_dates || [],
    opshopPickups: payload.opshop_pickups || [],
    assignedOpShopPickups: payload.assigned_opshop_pickups || [],
    scheduledOpShopPickups: payload.scheduled_opshop_pickups || [],
    oncallOpShopPickups: payload.oncall_opshop_pickups || [],
    countrysideOpShopPickups: payload.countryside_opshop_pickups || [],
    countrysideRouteGroups: payload.countryside_route_groups || [],
    generatedFinalTripSummaries: payload.generated_final_trip_summaries || [],
    opshopRegularListWindowStart: payload.opshop_regular_list_window_start || "",
    opshopRegularListWindowEnd: payload.opshop_regular_list_window_end || "",
    driverVehicleAssignments: (payload.driver_vehicle_assignments || []).map((assignment) => ({
      ...assignment,
      delivery_date: assignment.delivery_date || assignment.dispatch_date || payload.dispatch_date || state.dispatchDate,
    })),
  };
}


export function applyBoardResponse(payload, cleanupPendingSelections) {
  const board = normalizeBoardResponse(payload);
  state.dispatchDate = board.dispatchDate;
  if (!state.driverSummaryDeliveryDate) {
    state.driverSummaryDeliveryDate = board.dispatchDate;
  }
  state.orders = board.orders;
  state.drivers = board.drivers;
  state.vehicles = board.vehicles;
  state.assignments = board.assignments;
  state.finalizedDriverDeliveryDates = board.finalizedDriverDeliveryDates;
  state.opshopPickups = board.opshopPickups;
  state.assignedOpShopPickups = board.assignedOpShopPickups;
  state.scheduledOpShopPickups = board.scheduledOpShopPickups;
  state.oncallOpShopPickups = board.oncallOpShopPickups;
  state.countrysideOpShopPickups = board.countrysideOpShopPickups;
  state.countrysideRouteGroups = board.countrysideRouteGroups;
  state.opshopRegularListWindowStart = board.opshopRegularListWindowStart;
  state.opshopRegularListWindowEnd = board.opshopRegularListWindowEnd;
  state.driverVehicleAssignments = board.driverVehicleAssignments;
  applyGeneratedFinalSummaries(board.generatedFinalTripSummaries);
  cleanupPendingSelections();
}


function applyGeneratedFinalSummaries(generatedSummaries) {
  state.finalTripSummaries = {};
  state.generatedTaskKeys = new Set();

  (generatedSummaries || []).forEach((summary) => {
    const deliveryDate = summary.delivery_date || summary.dispatch_date || state.dispatchDate;
    const key = `${summary.driver_id || ""}:${deliveryDate || ""}`;
    state.finalTripSummaries[key] = summary;
    (summary.trips || []).forEach((trip) => {
      (trip.orders || []).forEach((order) => {
        const taskType = order.task_type || "ORDER";
        const taskId = order.task_id || order.order_id || order.order_id_snapshot || "";
        if (taskId) {
          state.generatedTaskKeys.add(`${taskType}:${taskId}`);
        }
      });
    });
    (summary.opshop_pickups || []).forEach((pickup) => {
      const pickupTaskId = pickup.pickup_task_id || pickup.pickup_task_id_snapshot || "";
      if (pickupTaskId) {
        state.generatedTaskKeys.add(`OPSHOP_PICKUP:${pickupTaskId}`);
      }
    });
  });
}
