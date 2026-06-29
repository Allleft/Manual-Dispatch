export function getDeliveryVehicleConflictDriverNames({
  board,
  claims,
  deliveryDate,
  driverId,
  vehicleId,
}) {
  if (!deliveryDate || !vehicleId) {
    return [];
  }

  const scopedBoard = board || {};
  const scopedClaims = claims || {};

  const driverNames = new Map(
    (scopedBoard.drivers || []).map((driver) => [
      driver.driver_id,
      driver.name || driver.driver_id,
    ]),
  );
  const savedAssignments = (scopedBoard.driver_vehicle_assignments || []).filter(
    (assignment) =>
      assignment.delivery_date === deliveryDate
      && assignment.vehicle_id === vehicleId,
  );
  const savedConflictDriverIds = savedAssignments
    .map((assignment) => assignment.driver_id)
    .filter((candidateDriverId) => candidateDriverId && candidateDriverId !== driverId);
  if (savedConflictDriverIds.length) {
    return savedConflictDriverIds.map(
      (candidateDriverId) => driverNames.get(candidateDriverId) || candidateDriverId,
    );
  }
  if (savedAssignments.some((assignment) => assignment.driver_id === driverId)) {
    return [];
  }

  const currentKey = `${deliveryDate}|${driverId}`;
  const currentClaim = scopedClaims[currentKey];
  const currentSequence = currentClaim?.vehicle_id === vehicleId
    ? Number(currentClaim.sequence)
    : Number.POSITIVE_INFINITY;
  const claimPrefix = `${deliveryDate}|`;
  const earlierClaim = Object.entries(scopedClaims)
    .filter(([key, claim]) =>
      key.startsWith(claimPrefix)
      && key !== currentKey
      && claim?.vehicle_id === vehicleId
      && Number(claim.sequence) < currentSequence,
    )
    .sort((left, right) => Number(left[1].sequence) - Number(right[1].sequence))[0];
  if (!earlierClaim) {
    return [];
  }
  const claimantDriverId = earlierClaim[0].slice(claimPrefix.length);
  return [driverNames.get(claimantDriverId) || claimantDriverId];
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
