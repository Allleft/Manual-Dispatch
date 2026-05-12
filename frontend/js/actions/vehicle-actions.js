import { apiAssignDriverVehicle } from "../api/manual-dispatch-api.js";

export function createVehicleActions({
  clearError,
  loadBoard,
  renderBoard,
  showError,
  state,
}) {
  async function handleVehicleChange(driverId, vehicleId) {
    if (state.isSaving) {
      return;
    }

    state.isSaving = true;
    clearError();
    renderBoard();

    try {
      await apiAssignDriverVehicle({
        dispatch_date: state.dispatchDate,
        driver_id: driverId,
        vehicle_id: vehicleId || null,
      });
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      showError(`Unable to update vehicle selection. ${error.message}`);
      renderBoard();
    }
  }

  return {
    handleVehicleChange,
  };
}
