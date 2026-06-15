import {
  apiApplyWeeklyOpShopPickupAssignments,
  apiCreateOpShopPickup,
  apiDeleteOpShopPickup,
  apiListOpShopPickupSchedules,
  apiUpdateOpShopPickup,
} from "../api/manual-dispatch-api.js";
import { isGeneratedTask } from "../state/selectors.js";
import {
  initializeCollapsedPickupDateGroups,
  toggleCollapsedPickupDateGroup,
} from "../utils/opshop-date-group-utils.js";
import {
  captureElementScroll,
  restoreElementScroll,
} from "../utils/scroll-utils.js";

export function createOpShopPickupActions({
  loadBoard,
  renderBoard,
  state,
}) {
  async function openOpShopPickupList() {
    state.isOpShopPickupListOpen = true;
    state.opshopPickupListError = "";
    state.opshopPickupFormMode = "";
    state.opshopPickupEditingTaskId = "";
    state.opshopPickupForm = {};
    initializeAssignedDriverSelections({ preserveExisting: false });
    initializeCollapsedDateGroups();
    renderBoard();
    await loadScheduleCandidates();
  }

  async function closeOpShopPickupList() {
    if (state.isOpShopPickupSaving || state.isOpShopPickupListLoading) {
      return;
    }
    state.isOpShopPickupSaving = true;
    state.opshopPickupListError = "";
    renderBoard();

    try {
      await apiApplyWeeklyOpShopPickupAssignments({
        dispatch_date: state.dispatchDate,
        assignments: state.scheduledOpShopPickups
          .filter((pickup) => !isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id))
          .map((pickup) => ({
            pickup_task_id: pickup.pickup_task_id,
            driver_id: state.opshopPickupAssignedDriverSelections[pickup.pickup_task_id] || "",
          })),
      });
      state.isOpShopPickupListOpen = false;
      state.opshopPickupFormMode = "";
      state.opshopPickupEditingTaskId = "";
      state.opshopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
    } catch (error) {
      state.opshopPickupListError = `Unable to apply OP SHOP pickup assignments. ${error.message}`;
    } finally {
      state.isOpShopPickupSaving = false;
      renderBoard();
    }
  }

  function closeOpShopPickupListWithoutApply() {
    state.isOpShopPickupListOpen = false;
    state.opshopPickupListError = "";
    state.opshopPickupFormMode = "";
    state.opshopPickupEditingTaskId = "";
    state.opshopPickupForm = {};
    renderBoard();
  }

  async function loadScheduleCandidates() {
    state.isOpShopPickupListLoading = true;
    state.opshopPickupListError = "";
    renderBoard();

    try {
      state.opshopPickupScheduleCandidates = await apiListOpShopPickupSchedules();
    } catch (error) {
      state.opshopPickupListError = `Unable to load OP SHOP schedules. ${error.message}`;
    } finally {
      state.isOpShopPickupListLoading = false;
      renderBoard();
    }
  }

  function startAddPickupTask() {
    state.opshopPickupFormMode = "add";
    state.opshopPickupEditingTaskId = "";
    state.opshopPickupForm = {
      schedule_id: "",
      pickup_date: state.dispatchDate,
      notes: "",
    };
    state.opshopPickupListError = "";
    renderBoard();
  }

  function startEditPickupTask(pickup) {
    state.opshopPickupFormMode = "edit";
    state.opshopPickupEditingTaskId = pickup.pickup_task_id;
    state.opshopPickupForm = {
      pickup_date: pickup.pickup_date || state.dispatchDate,
      notes: pickup.task_notes || "",
    };
    state.opshopPickupListError = "";
    renderBoard();
  }

  function startDeletePickupTask(pickup) {
    state.opshopPickupFormMode = "delete";
    state.opshopPickupEditingTaskId = pickup.pickup_task_id;
    state.opshopPickupForm = {};
    state.opshopPickupListError = "";
    renderBoard();
  }

  function cancelPickupTaskForm() {
    state.opshopPickupFormMode = "";
    state.opshopPickupEditingTaskId = "";
    state.opshopPickupForm = {};
    state.opshopPickupListError = "";
    renderBoard();
  }

  function updatePickupTaskForm(field, value) {
    state.opshopPickupForm = {
      ...state.opshopPickupForm,
      [field]: value,
    };
  }

  async function handleCreatePickupTask() {
    if (state.isOpShopPickupSaving) {
      return;
    }

    state.isOpShopPickupSaving = true;
    state.opshopPickupListError = "";
    renderBoard();

    try {
      await apiCreateOpShopPickup({
        schedule_id: state.opshopPickupForm.schedule_id,
        pickup_date: state.opshopPickupForm.pickup_date,
        notes: state.opshopPickupForm.notes || null,
      });
      state.opshopPickupFormMode = "";
      state.opshopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections({ preserveExisting: true });
    } catch (error) {
      state.opshopPickupListError = `Unable to add OP SHOP pickup. ${error.message}`;
    } finally {
      state.isOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function handleUpdatePickupTask() {
    if (state.isOpShopPickupSaving || !state.opshopPickupEditingTaskId) {
      return;
    }

    state.isOpShopPickupSaving = true;
    state.opshopPickupListError = "";
    renderBoard();

    try {
      await apiUpdateOpShopPickup(state.opshopPickupEditingTaskId, {
        pickup_date: state.opshopPickupForm.pickup_date,
        notes: state.opshopPickupForm.notes || null,
      });
      state.opshopPickupFormMode = "";
      state.opshopPickupEditingTaskId = "";
      state.opshopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections({ preserveExisting: true });
    } catch (error) {
      state.opshopPickupListError = `Unable to update OP SHOP pickup. ${error.message}`;
    } finally {
      state.isOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function handleDeletePickupTask() {
    if (state.isOpShopPickupSaving || !state.opshopPickupEditingTaskId) {
      return;
    }

    state.isOpShopPickupSaving = true;
    state.opshopPickupListError = "";
    renderBoard();

    try {
      await apiDeleteOpShopPickup(state.opshopPickupEditingTaskId);
      state.opshopPickupFormMode = "";
      state.opshopPickupEditingTaskId = "";
      state.opshopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections({ preserveExisting: true });
    } catch (error) {
      state.opshopPickupListError = `Unable to delete OP SHOP pickup. ${error.message}`;
    } finally {
      state.isOpShopPickupSaving = false;
      renderBoard();
    }
  }

  function updateAssignedDriverSelection(pickupTaskId, driverId) {
    state.opshopPickupAssignedDriverSelections = {
      ...state.opshopPickupAssignedDriverSelections,
      [pickupTaskId]: driverId,
    };
    renderBoard();
  }

  function toggleDateGroup(pickupDate) {
    const scrollSnapshot = captureElementScroll("#opshop-pickup-list-root");

    state.collapsedRegularOpShopPickupDates = toggleCollapsedPickupDateGroup(
      state.collapsedRegularOpShopPickupDates,
      pickupDate,
      state.dispatchDate,
    );
    renderBoard();
    restoreElementScroll(scrollSnapshot);
  }

  function shouldUseDefaultDriverForPickup(pickup) {
    return Boolean(
      pickup &&
      pickup.default_driver_id &&
      pickup.pickup_date &&
      state.dispatchDate &&
      pickup.pickup_date >= state.dispatchDate,
    );
  }

  function canUseDefaultDriverForPickup(pickup) {
    if (!shouldUseDefaultDriverForPickup(pickup)) {
      return false;
    }

    const defaultDriverExists = state.drivers.some(
      (driver) => driver.driver_id === pickup.default_driver_id,
    );
    if (!defaultDriverExists) {
      return false;
    }

    const hasSavedFinalSummary = state.finalizedDriverDeliveryDates.some(
      (lockedDate) =>
        lockedDate.driver_id === pickup.default_driver_id &&
        lockedDate.delivery_date === pickup.pickup_date,
    );

    return !hasSavedFinalSummary;
  }

  function initializeAssignedDriverSelections({ preserveExisting = false } = {}) {
    const existingSelections = preserveExisting ? state.opshopPickupAssignedDriverSelections || {} : {};
    const selections = {};
    state.scheduledOpShopPickups.forEach((pickup) => {
      const hasExistingSelection = Object.prototype.hasOwnProperty.call(
        existingSelections,
        pickup.pickup_task_id,
      );

      if (hasExistingSelection) {
        selections[pickup.pickup_task_id] = existingSelections[pickup.pickup_task_id];
        return;
      }

      selections[pickup.pickup_task_id] =
        pickup.assigned_driver_id ||
        pickup.driver_id ||
        (canUseDefaultDriverForPickup(pickup) ? pickup.default_driver_id : "") ||
        "";
    });
    state.opshopPickupAssignedDriverSelections = selections;
  }

  function initializeCollapsedDateGroups() {
    state.collapsedRegularOpShopPickupDates = initializeCollapsedPickupDateGroups(
      state.scheduledOpShopPickups,
      state.dispatchDate,
    );
  }

  return {
    cancelPickupTaskForm,
    closeOpShopPickupList,
    closeOpShopPickupListWithoutApply,
    handleCreatePickupTask,
    handleDeletePickupTask,
    handleUpdatePickupTask,
    loadScheduleCandidates,
    openOpShopPickupList,
    startAddPickupTask,
    startDeletePickupTask,
    startEditPickupTask,
    toggleDateGroup,
    updateAssignedDriverSelection,
    updatePickupTaskForm,
  };
}
