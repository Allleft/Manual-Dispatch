import {
  apiApplyCountrysideOpShopPickupAssignments,
  apiCreateOncallOpShopPickup,
  apiDeleteOpShopPickup,
  apiListCountrysideOpShopPickupSchedules,
  apiListCountrysideRouteGroups,
  apiUpdateOpShopPickup,
} from "../api/manual-dispatch-api.js";
import { isGeneratedTask } from "../state/selectors.js";
import {
  captureElementScroll,
  restoreElementScroll,
} from "../utils/scroll-utils.js";

export function createCountrysideOpShopPickupActions({
  loadBoard,
  renderBoard,
  state,
}) {
  async function openCountrysideOpShopPickupList() {
    state.isCountrysideOpShopPickupListOpen = true;
    state.countrysideOpShopPickupListError = "";
    state.countrysideOpShopPickupFormMode = "";
    state.countrysideOpShopPickupEditingTaskId = "";
    state.countrysideOpShopPickupForm = {};
    initializeAssignedDriverSelections();
    renderBoard();
    await Promise.all([loadRouteGroups(), loadScheduleCandidates()]);
  }

  async function closeCountrysideOpShopPickupList() {
    if (state.isCountrysideOpShopPickupSaving) {
      return;
    }
    state.isCountrysideOpShopPickupSaving = true;
    state.countrysideOpShopPickupListError = "";
    renderBoard();

    try {
      await apiApplyCountrysideOpShopPickupAssignments({
        dispatch_date: state.dispatchDate,
        assignments: getVisibleCountrysidePickups()
          .filter((pickup) => !isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id))
          .map((pickup) => ({
            pickup_task_id: pickup.pickup_task_id,
            driver_id:
              state.countrysideOpShopPickupAssignedDriverSelections[pickup.pickup_task_id] || "",
          })),
      });
      state.isCountrysideOpShopPickupListOpen = false;
      state.countrysideOpShopPickupFormMode = "";
      state.countrysideOpShopPickupEditingTaskId = "";
      state.countrysideOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
    } catch (error) {
      state.countrysideOpShopPickupListError = `Unable to apply Countryside OP SHOP pickup assignments. ${error.message}`;
    } finally {
      state.isCountrysideOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function loadRouteGroups() {
    state.isCountrysideOpShopPickupListLoading = true;
    state.countrysideOpShopPickupListError = "";
    renderBoard();

    try {
      state.countrysideRouteGroups = await apiListCountrysideRouteGroups();
    } catch (error) {
      state.countrysideOpShopPickupListError = `Unable to load Countryside route groups. ${error.message}`;
    } finally {
      state.isCountrysideOpShopPickupListLoading = false;
      renderBoard();
    }
  }

  async function loadScheduleCandidates() {
    state.isCountrysideOpShopPickupListLoading = true;
    state.countrysideOpShopPickupListError = "";
    renderBoard();

    try {
      state.countrysideOpShopPickupScheduleCandidates = await apiListCountrysideOpShopPickupSchedules();
    } catch (error) {
      state.countrysideOpShopPickupListError = `Unable to load Countryside OP SHOP templates. ${error.message}`;
    } finally {
      state.isCountrysideOpShopPickupListLoading = false;
      renderBoard();
    }
  }

  function startAddPickupTask() {
    state.countrysideOpShopPickupFormMode = "add";
    state.countrysideOpShopPickupEditingTaskId = "";
    state.countrysideOpShopPickupForm = {
      route_group_id: state.selectedCountrysideRouteGroupId || "",
      schedule_id: "",
      pickup_date: "",
      assigned_driver_id: "",
      notes: "",
    };
    state.countrysideOpShopPickupListError = "";
    renderBoard();
  }

  function startEditPickupTask(pickup) {
    state.countrysideOpShopPickupFormMode = "edit";
    state.countrysideOpShopPickupEditingTaskId = pickup.pickup_task_id;
    state.countrysideOpShopPickupForm = {
      pickup_date: pickup.pickup_date || state.dispatchDate,
      assigned_driver_id:
        state.countrysideOpShopPickupAssignedDriverSelections[pickup.pickup_task_id] ||
        pickup.assigned_driver_id ||
        pickup.driver_id ||
        pickup.default_driver_id ||
        "",
      notes: pickup.task_notes || "",
    };
    state.countrysideOpShopPickupListError = "";
    renderBoard();
  }

  function startDeletePickupTask(pickup) {
    state.countrysideOpShopPickupFormMode = "delete";
    state.countrysideOpShopPickupEditingTaskId = pickup.pickup_task_id;
    state.countrysideOpShopPickupForm = {};
    state.countrysideOpShopPickupListError = "";
    renderBoard();
  }

  function cancelPickupTaskForm() {
    state.countrysideOpShopPickupFormMode = "";
    state.countrysideOpShopPickupEditingTaskId = "";
    state.countrysideOpShopPickupForm = {};
    state.countrysideOpShopPickupListError = "";
    renderBoard();
  }

  function updatePickupTaskForm(field, value) {
    const nextForm = {
      ...state.countrysideOpShopPickupForm,
      [field]: value,
    };
    if (field === "route_group_id") {
      nextForm.schedule_id = "";
      nextForm.assigned_driver_id = "";
    }
    if (field === "schedule_id") {
      const candidate = state.countrysideOpShopPickupScheduleCandidates.find(
        (item) => item.schedule_id === value,
      );
      nextForm.route_group_id = candidate ? candidate.route_group_id || "" : nextForm.route_group_id;
      nextForm.assigned_driver_id = candidate ? candidate.default_driver_id || "" : "";
    }
    state.countrysideOpShopPickupForm = nextForm;
    renderBoard();
  }

  async function handleCreatePickupTask() {
    if (state.isCountrysideOpShopPickupSaving) {
      return;
    }

    state.isCountrysideOpShopPickupSaving = true;
    state.countrysideOpShopPickupListError = "";
    renderBoard();

    try {
      const selectedDriverId = state.countrysideOpShopPickupForm.assigned_driver_id || "";
      const created = await apiCreateOncallOpShopPickup({
        schedule_id: state.countrysideOpShopPickupForm.schedule_id,
        pickup_date: state.countrysideOpShopPickupForm.pickup_date,
        assigned_driver_id: selectedDriverId || null,
        notes: state.countrysideOpShopPickupForm.notes || null,
      });
      state.countrysideOpShopPickupFormMode = "";
      state.countrysideOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections();
      if (created && created.pickup_task_id) {
        state.countrysideOpShopPickupAssignedDriverSelections = {
          ...state.countrysideOpShopPickupAssignedDriverSelections,
          [created.pickup_task_id]: selectedDriverId,
        };
      }
    } catch (error) {
      state.countrysideOpShopPickupListError = `Unable to add Countryside OP SHOP pickup. ${error.message}`;
    } finally {
      state.isCountrysideOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function handleUpdatePickupTask() {
    if (state.isCountrysideOpShopPickupSaving || !state.countrysideOpShopPickupEditingTaskId) {
      return;
    }

    state.isCountrysideOpShopPickupSaving = true;
    state.countrysideOpShopPickupListError = "";
    renderBoard();

    try {
      const pickupTaskId = state.countrysideOpShopPickupEditingTaskId;
      const selectedDriverId = state.countrysideOpShopPickupForm.assigned_driver_id || "";
      await apiUpdateOpShopPickup(pickupTaskId, {
        pickup_date: state.countrysideOpShopPickupForm.pickup_date,
        notes: state.countrysideOpShopPickupForm.notes || null,
      });
      state.countrysideOpShopPickupFormMode = "";
      state.countrysideOpShopPickupEditingTaskId = "";
      state.countrysideOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections();
      state.countrysideOpShopPickupAssignedDriverSelections = {
        ...state.countrysideOpShopPickupAssignedDriverSelections,
        [pickupTaskId]: selectedDriverId,
      };
    } catch (error) {
      state.countrysideOpShopPickupListError = `Unable to update Countryside OP SHOP pickup. ${error.message}`;
    } finally {
      state.isCountrysideOpShopPickupSaving = false;
      renderBoard();
    }
  }

  async function handleDeletePickupTask() {
    if (state.isCountrysideOpShopPickupSaving || !state.countrysideOpShopPickupEditingTaskId) {
      return;
    }

    state.isCountrysideOpShopPickupSaving = true;
    state.countrysideOpShopPickupListError = "";
    renderBoard();

    try {
      await apiDeleteOpShopPickup(state.countrysideOpShopPickupEditingTaskId);
      state.countrysideOpShopPickupFormMode = "";
      state.countrysideOpShopPickupEditingTaskId = "";
      state.countrysideOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections();
    } catch (error) {
      state.countrysideOpShopPickupListError = `Unable to delete Countryside OP SHOP pickup. ${error.message}`;
    } finally {
      state.isCountrysideOpShopPickupSaving = false;
      renderBoard();
    }
  }

  function updateAssignedDriverSelection(pickupTaskId, driverId) {
    state.countrysideOpShopPickupAssignedDriverSelections = {
      ...state.countrysideOpShopPickupAssignedDriverSelections,
      [pickupTaskId]: driverId,
    };
    renderBoard();
  }

  function setSelectedRouteGroup(routeGroupId) {
    const scrollSnapshot = captureElementScroll("#opshop-countryside-pickup-list-root");
    state.selectedCountrysideRouteGroupId = routeGroupId || "";
    renderBoard();
    restoreElementScroll(scrollSnapshot);
  }

  function initializeAssignedDriverSelections() {
    const selections = {};
    state.countrysideOpShopPickups.forEach((pickup) => {
      selections[pickup.pickup_task_id] =
        pickup.assigned_driver_id ||
        pickup.driver_id ||
        pickup.default_driver_id ||
        "";
    });
    state.countrysideOpShopPickupAssignedDriverSelections = selections;
  }

  function getVisibleCountrysidePickups() {
    return state.countrysideOpShopPickups.filter(
      (pickup) =>
        !state.selectedCountrysideRouteGroupId ||
        pickup.route_group_id === state.selectedCountrysideRouteGroupId,
    );
  }

  return {
    cancelPickupTaskForm,
    closeCountrysideOpShopPickupList,
    handleCreatePickupTask,
    handleDeletePickupTask,
    handleUpdatePickupTask,
    loadRouteGroups,
    loadScheduleCandidates,
    openCountrysideOpShopPickupList,
    setSelectedRouteGroup,
    startAddPickupTask,
    startDeletePickupTask,
    startEditPickupTask,
    updateAssignedDriverSelection,
    updatePickupTaskForm,
  };
}
