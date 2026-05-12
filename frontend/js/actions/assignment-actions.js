import {
  apiAssignTask,
  apiUnassignTask,
} from "../api/manual-dispatch-api.js";

export function createAssignmentActions({
  clearError,
  closeOrderDetail,
  loadBoard,
  renderBoard,
  showError,
  state,
}) {
  function getPendingSelection(orderId) {
    if (!state.pendingSelections[orderId]) {
      state.pendingSelections[orderId] = { driver_id: "", trip_no: "trip1" };
    }
    return state.pendingSelections[orderId];
  }

  function updatePendingSelection(orderId, updates) {
    const current = getPendingSelection(orderId);
    state.pendingSelections[orderId] = {
      ...current,
      ...updates,
    };
  }

  function cleanupPendingSelections() {
    const orderIds = new Set(state.orders.map((order) => order.order_id));
    const assignedOrderIds = new Set(
      state.assignments
        .filter((assignment) => assignment.task_type === "ORDER")
        .map((assignment) => assignment.task_id),
    );
    const driverIds = new Set(state.drivers.map((driver) => driver.driver_id));

    Object.entries(state.pendingSelections).forEach(([orderId, selection]) => {
      if (!orderIds.has(orderId) || assignedOrderIds.has(orderId)) {
        delete state.pendingSelections[orderId];
        return;
      }

      if (selection.driver_id && !driverIds.has(selection.driver_id)) {
        selection.driver_id = "";
      }

      if (!["trip1", "trip2"].includes(selection.trip_no)) {
        selection.trip_no = "trip1";
      }
    });
  }

  async function handleAssign(orderId) {
    const selection = getPendingSelection(orderId);
    if (!selection.driver_id || state.isSaving) {
      return;
    }

    state.isSaving = true;
    clearError();
    renderBoard();

    try {
      await apiAssignTask({
        dispatch_date: state.dispatchDate,
        task_type: "ORDER",
        task_id: orderId,
        driver_id: selection.driver_id,
        trip_no: selection.trip_no || "trip1",
      });
      delete state.pendingSelections[orderId];
      closeOrderDetail();
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      showError(`Unable to assign task. ${error.message}`);
      renderBoard();
    }
  }

  async function handleUnassign(taskType, taskId) {
    if (state.isSaving) {
      return;
    }

    state.isSaving = true;
    clearError();
    renderBoard();

    try {
      await apiUnassignTask({
        dispatch_date: state.dispatchDate,
        task_type: taskType,
        task_id: taskId,
      });
      updatePendingSelection(taskId, { driver_id: "", trip_no: "trip1" });
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      showError(`Unable to unassign task. ${error.message}`);
      renderBoard();
    }
  }

  return {
    cleanupPendingSelections,
    getPendingSelection,
    handleAssign,
    handleUnassign,
    updatePendingSelection,
  };
}
