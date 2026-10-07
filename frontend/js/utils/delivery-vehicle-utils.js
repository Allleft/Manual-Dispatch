export const DELIVERY_VEHICLE_TRIPS = ["trip1", "trip2"];

export function deliveryVehicleKey(deliveryDate, driverId, tripNo) {
  if (!deliveryDate || !driverId || !DELIVERY_VEHICLE_TRIPS.includes(tripNo)
      || deliveryDate.includes("|") || driverId.includes("|")) {
    throw new Error("Delivery vehicle selection requires date, driver and trip1/trip2.");
  }
  return `${deliveryDate}|${driverId}|${tripNo}`;
}

export function parseDeliveryVehicleKey(key) {
  const parts = String(key).split("|");
  if (parts.length !== 3 || !parts[0] || !parts[1] || !DELIVERY_VEHICLE_TRIPS.includes(parts[2])) {
    return null;
  }
  return { deliveryDate: parts[0], driverId: parts[1], tripNo: parts[2] };
}

export function getDeliveryTripVehicleAssignment(board, deliveryDate, driverId, tripNo) {
  deliveryVehicleKey(deliveryDate, driverId, tripNo);
  return (board?.driver_vehicle_assignments || []).find((row) =>
    row.delivery_date === deliveryDate && row.driver_id === driverId && row.trip_no === tripNo);
}

// Stage 3 retires these day projections when controls and generation switch together.
export function getDeliveryDayVehicleAssignment(board, deliveryDate, driverId) {
  const trips = (board?.driver_vehicle_assignments || []).filter((row) =>
    row.delivery_date === deliveryDate && row.driver_id === driverId);
  if (trips.length) {
    const first = getDeliveryTripVehicleAssignment(board, deliveryDate, driverId, "trip1");
    const second = getDeliveryTripVehicleAssignment(board, deliveryDate, driverId, "trip2");
    return trips.length === 2 && first && second && first.vehicle_id === second.vehicle_id ? first : null;
  }
  return (board?.legacy_driver_vehicle_assignments || []).find((row) =>
    row.delivery_date === deliveryDate && row.driver_id === driverId && row.trip_no == null);
}

export function getDeliveryDayVehicleDraft(drafts, deliveryDate, driverId) {
  const values = DELIVERY_VEHICLE_TRIPS.map((tripNo) => drafts?.[deliveryVehicleKey(deliveryDate, driverId, tripNo)]);
  return values[0] === values[1] ? values[0] : undefined;
}

export function getDeliveryVehicleConflictDriverNames({
  board, claims, deliveryDate, driverId, tripNo, vehicleId,
}) {
  if (!deliveryDate || !vehicleId) {
    return [];
  }
  deliveryVehicleKey(deliveryDate, driverId, tripNo);
  const driverNames = new Map((board?.drivers || []).map((driver) => [driver.driver_id, driver.name]));
  const savedAssignments = (board?.driver_vehicle_assignments || []).filter((row) =>
    row.delivery_date === deliveryDate && row.trip_no === tripNo && row.vehicle_id === vehicleId);
  const conflictIds = savedAssignments.filter((row) => row.driver_id !== driverId).map((row) => row.driver_id);
  if (conflictIds.length) {
    return [...new Set(conflictIds)].map((id) => driverNames.get(id) || id);
  }
  if (savedAssignments.some((row) => row.driver_id === driverId)) {
    return [];
  }
  const key = deliveryVehicleKey(deliveryDate, driverId, tripNo);
  const currentClaim = claims?.[key];
  const currentSequence = currentClaim?.vehicle_id === vehicleId ? Number(currentClaim.sequence || 0) : Infinity;
  const earlier = Object.entries(claims || {})
    .map(([claimKey, claim]) => ({ scope: parseDeliveryVehicleKey(claimKey), claim }))
    .filter(({ scope, claim }) => scope && scope.deliveryDate === deliveryDate
      && scope.tripNo === tripNo && scope.driverId !== driverId
      && claim?.vehicle_id === vehicleId && Number(claim.sequence || 0) < currentSequence)
    .sort((left, right) => Number(left.claim.sequence || 0) - Number(right.claim.sequence || 0))[0];
  return earlier ? [driverNames.get(earlier.scope.driverId) || earlier.scope.driverId] : [];
}

export function getDeliveryDayVehicleConflictDriverNames(input) {
  const board = input.board || {};
  const legacy = (board.legacy_driver_vehicle_assignments || []).filter((row) =>
    !(board.driver_vehicle_assignments || []).some((trip) =>
      trip.delivery_date === row.delivery_date && trip.driver_id === row.driver_id));
  const compatibilityBoard = {
    ...board,
    driver_vehicle_assignments: (board.driver_vehicle_assignments || []).concat(
      legacy.flatMap((row) => DELIVERY_VEHICLE_TRIPS.map((trip_no) => ({ ...row, trip_no }))),
    ),
  };
  return [...new Set(DELIVERY_VEHICLE_TRIPS.flatMap((tripNo) =>
    getDeliveryVehicleConflictDriverNames({ ...input, board: compatibilityBoard, tripNo })))];
}

export function formatDeliveryVehicleConflictMessage(driverNames) {
  const names = Array.from(new Set(driverNames || []));
  if (!names.length) {
    return "";
  }
  if (names.length === 1) {
    return `This vehicle is already assigned to ${names[0]}.`;
  }
  return `This vehicle is already assigned to: ${names.join(", ")}.`;
}


export function formatDeliveryVehicleOptionLabel(vehicle, conflictDriverNames = []) {
  const rego = vehicle?.rego || vehicle?.vehicle_id || "Unknown vehicle";
  const capacity = Number(vehicle?.pallet_capacity || 0);
  const assignedSuffix = conflictDriverNames.length
    ? ` — assigned to ${conflictDriverNames.join(", ")}`
    : "";
  return `${rego} — ${capacity} pallet capacity${assignedSuffix}`;
}
