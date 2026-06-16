import {
  apiAssignTask,
  apiUnassignTask,
} from "../api/manual-dispatch-api.js";
import { getTaskKey } from "../state/selectors.js";

export function createAssignmentActions({
  clearError,
  closeOpShopPickupDetail,
  closeOrderDetail,
  loadBoard,
  renderBoard,
  showError,
  state,
}) {
  function getPendingSelection(taskType, taskId) {
    const key = getTaskKey(taskType, taskId);
    if (!state.pendingSelections[key]) {
      state.pendingSelections[key] = { driver_id: "", trip_no: "trip1" };
    }
    return state.pendingSelections[key];
  }

  function updatePendingSelection(taskType, taskId, updates) {
    const key = getTaskKey(taskType, taskId);
    const current = getPendingSelection(taskType, taskId);
    state.pendingSelections[key] = {
      ...current,
      ...updates,
    };
  }

  function cleanupPendingSelections() {
    const taskKeys = new Set([
      ...state.orders.map((order) => getTaskKey("ORDER", order.order_id)),
      ...state.opshopPickups.map((pickup) => getTaskKey("OPSHOP_PICKUP", pickup.pickup_task_id)),
    ]);
    const assignedTaskKeys = new Set(
      state.assignments.map((assignment) => getTaskKey(assignment.task_type, assignment.task_id)),
    );
    const driverIds = new Set(state.drivers.map((driver) => driver.driver_id));

    Object.entries(state.pendingSelections).forEach(([taskKey, selection]) => {
      if (!taskKeys.has(taskKey) || assignedTaskKeys.has(taskKey)) {
        delete state.pendingSelections[taskKey];
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
    return handleAssignTask("ORDER", orderId);
  }

  async function handleAssignTask(taskType, taskId) {
    const selection = getPendingSelection(taskType, taskId);
    if (!selection.driver_id || state.isSaving) {
      return;
    }

    state.isSaving = true;
    clearError();
    renderBoard();

    try {
      await apiAssignTask({
        dispatch_date: state.dispatchDate,
        task_type: taskType,
        task_id: taskId,
        driver_id: selection.driver_id,
        trip_no: selection.trip_no || "trip1",
      });
      delete state.pendingSelections[getTaskKey(taskType, taskId)];
      if (taskType === "ORDER") {
        closeOrderDetail();
      }
      if (taskType === "OPSHOP_PICKUP" && closeOpShopPickupDetail) {
        closeOpShopPickupDetail();
      }
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
    const taskIds = Array.isArray(taskId) ? taskId : [taskId];
    if (taskIds.length === 0) {
      return;
    }

    state.isSaving = true;
    clearError();
    renderBoard();

    try {
      await Promise.all(
        taskIds.map((currentTaskId) =>
          apiUnassignTask({
            dispatch_date: state.dispatchDate,
            task_type: taskType,
            task_id: currentTaskId,
          }),
        ),
      );
      taskIds.forEach((currentTaskId) => {
        updatePendingSelection(taskType, currentTaskId, { driver_id: "", trip_no: "trip1" });
      });
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
    handleAssignTask,
    handleUnassign,
    updatePendingSelection,
  };
}
