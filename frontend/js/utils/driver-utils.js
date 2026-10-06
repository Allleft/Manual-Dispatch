export function driversForAssignment(drivers, currentDriverId = "") {
  return (drivers || []).filter((driver) =>
    driver.is_available !== false || driver.driver_id === currentDriverId,
  );
}
