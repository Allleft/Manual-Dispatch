export function getDeliveryVehicleConflictDriverNames({
  board,
  drafts,
  deliveryDate,
  driverId,
  vehicleId,
}) {
  if (!deliveryDate || !vehicleId) {
    return [];
  }

  const scopedBoard = board || {};
  const scopedDrafts = drafts || {};
  const driverIds = new Set(
    (scopedBoard.drivers || []).map((driver) => driver.driver_id),
  );
  (scopedBoard.driver_vehicle_assignments || []).forEach((assignment) => {
    if (assignment.delivery_date === deliveryDate) {
      driverIds.add(assignment.driver_id);
    }
  });
  const draftPrefix = `${deliveryDate}|`;
  Object.keys(scopedDrafts).forEach((key) => {
    if (key.startsWith(draftPrefix)) {
      driverIds.add(key.slice(draftPrefix.length));
    }
  });

  const driverNames = new Map(
    (scopedBoard.drivers || []).map((driver) => [
      driver.driver_id,
      driver.name || driver.driver_id,
    ]),
  );
  return Array.from(driverIds)
    .filter((candidateDriverId) => candidateDriverId && candidateDriverId !== driverId)
    .filter((candidateDriverId) => {
      const savedConflict = (scopedBoard.driver_vehicle_assignments || []).some(
        (assignment) =>
          assignment.delivery_date === deliveryDate
          && assignment.driver_id === candidateDriverId
          && assignment.vehicle_id === vehicleId,
      );
      const draftKey = `${deliveryDate}|${candidateDriverId}`;
      const draftConflict = Object.prototype.hasOwnProperty.call(scopedDrafts, draftKey)
        && scopedDrafts[draftKey] === vehicleId;
      return savedConflict || draftConflict;
    })
    .map((candidateDriverId) => driverNames.get(candidateDriverId) || candidateDriverId);
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
