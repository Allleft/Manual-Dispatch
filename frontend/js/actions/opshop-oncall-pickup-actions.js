import {
  apiApplyOncallOpShopPickupAssignments,
  apiCreateOncallOpShopPickup,
  apiDeleteOpShopPickup,
  apiListOncallOpShopPickupSchedules,
  apiUpdateOpShopPickup,
} from "../api/manual-dispatch-api.js";

const WEEKDAY_OFFSETS = {
  MONDAY: 0,
  TUESDAY: 1,
  WEDNESDAY: 2,
  THURSDAY: 3,
  FRIDAY: 4,
};

export function createOncallOpShopPickupActions({
  loadBoard,
  renderBoard,
  state,
}) {
  async function openOncallOpShopPickupList() {
    state.isOncallOpShopPickupListOpen = true;
    state.oncallOpShopPickupListError = "";
    state.oncallOpShopPickupFormMode = "";
    state.oncallOpShopPickupEditingTaskId = "";
    state.oncallOpShopPickupForm = {};
    initializeAssignedDriverSelections();
    renderBoard();
    await loadScheduleCandidates();
  }

  async function closeOncallOpShopPickupList() {
    if (state.isOncallOpShopPickupSaving) {
      return;
    }
    state.isOncallOpShopPickupSaving = true;
    state.oncallOpShopPickupListError = "";
    renderBoard();

    try {
      await apiApplyOncallOpShopPickupAssignments({
        dispatch_date: state.dispatchDate,
        assignments: state.oncallOpShopPickups.map((pickup) => ({
          pickup_task_id: pickup.pickup_task_id,
          driver_id: state.oncallOpShopPickupAssignedDriverSelections[pickup.pickup_task_id] || "",
        })),
      });
      state.isOncallOpShopPickupListOpen = false;
      state.oncallOpShopPickupFormMode = "";
      state.oncallOpShopPickupEditingTaskId = "";
      state.oncallOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
    } catch (error) {
      state.oncallOpShopPickupListError = `Unable to apply Oncall OP SHOP pickup assignments. ${error.message}`;
    } finally {
      state.isOncallOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function loadScheduleCandidates() {
    state.isOncallOpShopPickupListLoading = true;
    state.oncallOpShopPickupListError = "";
    renderBoard();

    try {
      state.oncallOpShopPickupScheduleCandidates = await apiListOncallOpShopPickupSchedules();
    } catch (error) {
      state.oncallOpShopPickupListError = `Unable to load Oncall OP SHOP templates. ${error.message}`;
    } finally {
      state.isOncallOpShopPickupListLoading = false;
      renderBoard();
    }
  }

  function startAddPickupTask() {
    state.oncallOpShopPickupFormMode = "add";
    state.oncallOpShopPickupEditingTaskId = "";
    state.oncallOpShopPickupForm = {
      schedule_id: "",
      pickup_date: "",
      assigned_driver_id: "",
      notes: "",
    };
    state.oncallOpShopPickupListError = "";
    renderBoard();
  }

  function startEditPickupTask(pickup) {
    state.oncallOpShopPickupFormMode = "edit";
    state.oncallOpShopPickupEditingTaskId = pickup.pickup_task_id;
    state.oncallOpShopPickupForm = {
      pickup_date: pickup.pickup_date || state.dispatchDate,
      assigned_driver_id:
        state.oncallOpShopPickupAssignedDriverSelections[pickup.pickup_task_id] ||
        pickup.assigned_driver_id ||
        pickup.driver_id ||
        pickup.default_driver_id ||
        "",
      notes: pickup.task_notes || "",
    };
    state.oncallOpShopPickupListError = "";
    renderBoard();
  }

  function startDeletePickupTask(pickup) {
    state.oncallOpShopPickupFormMode = "delete";
    state.oncallOpShopPickupEditingTaskId = pickup.pickup_task_id;
    state.oncallOpShopPickupForm = {};
    state.oncallOpShopPickupListError = "";
    renderBoard();
  }

  function cancelPickupTaskForm() {
    state.oncallOpShopPickupFormMode = "";
    state.oncallOpShopPickupEditingTaskId = "";
    state.oncallOpShopPickupForm = {};
    state.oncallOpShopPickupListError = "";
    renderBoard();
  }

  function updatePickupTaskForm(field, value) {
    const nextForm = {
      ...state.oncallOpShopPickupForm,
      [field]: value,
    };
    if (field === "schedule_id") {
      const candidate = state.oncallOpShopPickupScheduleCandidates.find(
        (item) => item.schedule_id === value,
      );
      nextForm.pickup_date = getDefaultPickupDateForCandidate(candidate);
      nextForm.assigned_driver_id = candidate ? candidate.default_driver_id || "" : "";
    }
    state.oncallOpShopPickupForm = nextForm;
    renderBoard();
  }

  async function handleCreatePickupTask() {
    if (state.isOncallOpShopPickupSaving) {
      return;
    }

    state.isOncallOpShopPickupSaving = true;
    state.oncallOpShopPickupListError = "";
    renderBoard();

    try {
      const selectedDriverId = state.oncallOpShopPickupForm.assigned_driver_id || "";
      const created = await apiCreateOncallOpShopPickup({
        schedule_id: state.oncallOpShopPickupForm.schedule_id,
        pickup_date: state.oncallOpShopPickupForm.pickup_date,
        assigned_driver_id: selectedDriverId || null,
        notes: state.oncallOpShopPickupForm.notes || null,
      });
      state.oncallOpShopPickupFormMode = "";
      state.oncallOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections();
      if (created && created.pickup_task_id) {
        state.oncallOpShopPickupAssignedDriverSelections = {
          ...state.oncallOpShopPickupAssignedDriverSelections,
          [created.pickup_task_id]: selectedDriverId,
        };
      }
    } catch (error) {
      state.oncallOpShopPickupListError = `Unable to add Oncall OP SHOP pickup. ${error.message}`;
    } finally {
      state.isOncallOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function handleUpdatePickupTask() {
    if (state.isOncallOpShopPickupSaving || !state.oncallOpShopPickupEditingTaskId) {
      return;
    }

    state.isOncallOpShopPickupSaving = true;
    state.oncallOpShopPickupListError = "";
    renderBoard();

    try {
      const pickupTaskId = state.oncallOpShopPickupEditingTaskId;
      const selectedDriverId = state.oncallOpShopPickupForm.assigned_driver_id || "";
      await apiUpdateOpShopPickup(state.oncallOpShopPickupEditingTaskId, {
        pickup_date: state.oncallOpShopPickupForm.pickup_date,
        notes: state.oncallOpShopPickupForm.notes || null,
      });
      state.oncallOpShopPickupFormMode = "";
      state.oncallOpShopPickupEditingTaskId = "";
      state.oncallOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections();
      if (pickupTaskId) {
        state.oncallOpShopPickupAssignedDriverSelections = {
          ...state.oncallOpShopPickupAssignedDriverSelections,
          [pickupTaskId]: selectedDriverId,
        };
      }
    } catch (error) {
      state.oncallOpShopPickupListError = `Unable to update Oncall OP SHOP pickup. ${error.message}`;
    } finally {
      state.isOncallOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function handleDeletePickupTask() {
    if (state.isOncallOpShopPickupSaving || !state.oncallOpShopPickupEditingTaskId) {
      return;
    }

    state.isOncallOpShopPickupSaving = true;
    state.oncallOpShopPickupListError = "";
    renderBoard();

    try {
      await apiDeleteOpShopPickup(state.oncallOpShopPickupEditingTaskId);
      state.oncallOpShopPickupFormMode = "";
      state.oncallOpShopPickupEditingTaskId = "";
      state.oncallOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections();
    } catch (error) {
      state.oncallOpShopPickupListError = `Unable to delete Oncall OP SHOP pickup. ${error.message}`;
    } finally {
      state.isOncallOpShopPickupSaving = false;
      renderBoard();
    }
  }

  function updateAssignedDriverSelection(pickupTaskId, driverId) {
    state.oncallOpShopPickupAssignedDriverSelections = {
      ...state.oncallOpShopPickupAssignedDriverSelections,
      [pickupTaskId]: driverId,
    };
    renderBoard();
  }

  function initializeAssignedDriverSelections() {
    const selections = {};
    state.oncallOpShopPickups.forEach((pickup) => {
      selections[pickup.pickup_task_id] =
        pickup.assigned_driver_id ||
        pickup.driver_id ||
        pickup.default_driver_id ||
        "";
    });
    state.oncallOpShopPickupAssignedDriverSelections = selections;
  }

  function getDefaultPickupDateForCandidate(candidate) {
    if (!candidate || !candidate.run_day || !(candidate.run_day in WEEKDAY_OFFSETS)) {
      return "";
    }
    const monday = parseLocalDate(state.opshopRegularListWindowStart || state.dispatchDate);
    if (!monday) {
      return "";
    }
    const date = new Date(monday);
    date.setDate(monday.getDate() + WEEKDAY_OFFSETS[candidate.run_day]);
    return formatLocalDate(date);
  }

  return {
    cancelPickupTaskForm,
    closeOncallOpShopPickupList,
    handleCreatePickupTask,
    handleDeletePickupTask,
    handleUpdatePickupTask,
    loadScheduleCandidates,
    openOncallOpShopPickupList,
    startAddPickupTask,
    startDeletePickupTask,
    startEditPickupTask,
    updateAssignedDriverSelection,
    updatePickupTaskForm,
  };
}

function parseLocalDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) {
    return null;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function formatLocalDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
