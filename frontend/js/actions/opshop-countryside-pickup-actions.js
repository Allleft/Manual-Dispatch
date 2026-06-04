import {
  apiAddCountrysideRouteMembership,
  apiApplyCountrysideOpShopPickupAssignments,
  apiAssignCountrysideRouteGroup,
  apiCreateCountrysideRouteGroup,
  apiDeleteOpShopPickup,
  apiDisableCountrysideRouteGroup,
  apiListCountrysideOpShopPickupSchedules,
  apiListCountrysideRouteMemberships,
  apiListCountrysideRouteGroups,
  apiMoveCountrysideRouteMembership,
  apiRemoveCountrysideRouteMembership,
  apiUpdateCountrysideRouteGroup,
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
    state.countrysideRouteManagementError = "";
    state.countrysideOpShopPickupFormMode = "";
    state.countrysideOpShopPickupEditingTaskId = "";
    state.countrysideOpShopPickupForm = {};
    resetRouteGroupForm();
    resetRouteTemplateForm();
    initializeAssignedDriverSelections();
    renderBoard();
    await Promise.all([loadRouteGroups(), loadScheduleCandidates(), loadRouteMemberships()]);
  }

  async function closeCountrysideOpShopPickupList() {
    if (state.isCountrysideOpShopPickupSaving || state.isCountrysideOpShopPickupListLoading) {
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
      resetRouteGroupForm();
      resetRouteTemplateForm();
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

  async function loadRouteMemberships() {
    if (!state.selectedCountrysideRouteGroupId) {
      state.countrysideRouteMemberships = [];
      renderBoard();
      return;
    }

    state.isCountrysideOpShopPickupListLoading = true;
    state.countrysideRouteManagementError = "";
    renderBoard();

    try {
      state.countrysideRouteMemberships = await apiListCountrysideRouteMemberships(
        state.selectedCountrysideRouteGroupId,
      );
    } catch (error) {
      state.countrysideRouteManagementError = `Unable to load Countryside route templates. ${error.message}`;
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
      pickup_date: state.dispatchDate || "",
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

  function startNewRouteGroup() {
    state.countrysideRouteFormMode = "new";
    state.isCountrysideRouteFormOpen = true;
    state.countrysideRouteForm = {
      route_group_name: "",
    };
    state.countrysideRouteManagementError = "";
    resetRouteTemplateForm();
    renderBoard();
  }

  function startRenameRouteGroup() {
    const routeGroup = getSelectedRouteGroup();
    if (!routeGroup) {
      state.countrysideRouteManagementError = "Select a route group before renaming it.";
      renderBoard();
      return;
    }
    state.countrysideRouteFormMode = "rename";
    state.isCountrysideRouteFormOpen = true;
    state.countrysideRouteForm = {
      route_group_name: routeGroup.route_group_name || "",
    };
    state.countrysideRouteManagementError = "";
    resetRouteTemplateForm();
    renderBoard();
  }

  function startDisableRouteGroup() {
    const routeGroup = getSelectedRouteGroup();
    if (!routeGroup) {
      state.countrysideRouteManagementError = "Select a route group before disabling it.";
      renderBoard();
      return;
    }
    state.countrysideRouteFormMode = "disable";
    state.isCountrysideRouteFormOpen = true;
    state.countrysideRouteForm = {
      route_group_name: routeGroup.route_group_name || "",
    };
    state.countrysideRouteManagementError = "";
    resetRouteTemplateForm();
    renderBoard();
  }

  function cancelRouteGroupForm() {
    resetRouteGroupForm();
    state.countrysideRouteManagementError = "";
    renderBoard();
  }

  function updateRouteGroupForm(field, value) {
    state.countrysideRouteForm = {
      ...state.countrysideRouteForm,
      [field]: value,
    };
  }

  async function handleCreateRouteGroup() {
    if (state.isCountrysideRouteTemplateSaving) {
      return;
    }
    state.isCountrysideRouteTemplateSaving = true;
    state.countrysideRouteManagementError = "";
    renderBoard();

    try {
      const routeGroup = await apiCreateCountrysideRouteGroup({
        route_group_name: state.countrysideRouteForm.route_group_name,
      });
      state.selectedCountrysideRouteGroupId = routeGroup.route_group_id;
      resetRouteGroupForm();
      resetRouteTemplateForm();
      await refreshCountrysideRouteData();
    } catch (error) {
      state.countrysideRouteManagementError = `Unable to create Countryside route group. ${error.message}`;
    } finally {
      state.isCountrysideRouteTemplateSaving = false;
      renderBoard();
    }
  }

  async function handleRenameRouteGroup() {
    const routeGroup = getSelectedRouteGroup();
    if (state.isCountrysideRouteTemplateSaving || !routeGroup) {
      return;
    }
    state.isCountrysideRouteTemplateSaving = true;
    state.countrysideRouteManagementError = "";
    renderBoard();

    try {
      await apiUpdateCountrysideRouteGroup(routeGroup.route_group_id, {
        route_group_name: state.countrysideRouteForm.route_group_name,
      });
      resetRouteGroupForm();
      await refreshCountrysideRouteData();
    } catch (error) {
      state.countrysideRouteManagementError = `Unable to rename Countryside route group. ${error.message}`;
    } finally {
      state.isCountrysideRouteTemplateSaving = false;
      renderBoard();
    }
  }

  async function handleDisableRouteGroup() {
    const routeGroup = getSelectedRouteGroup();
    if (state.isCountrysideRouteTemplateSaving || !routeGroup) {
      return;
    }
    state.isCountrysideRouteTemplateSaving = true;
    state.countrysideRouteManagementError = "";
    renderBoard();

    try {
      await apiDisableCountrysideRouteGroup(routeGroup.route_group_id);
      state.selectedCountrysideRouteGroupId = "";
      resetRouteGroupForm();
      resetRouteTemplateForm();
      await refreshCountrysideRouteData();
    } catch (error) {
      state.countrysideRouteManagementError = `Unable to disable Countryside route group. ${error.message}`;
    } finally {
      state.isCountrysideRouteTemplateSaving = false;
      renderBoard();
    }
  }

  function startAddRouteTemplate() {
    const routeGroup = getSelectedRouteGroup();
    if (!routeGroup) {
      state.countrysideRouteManagementError = "Select a route group before adding an OP SHOP template.";
      renderBoard();
      return;
    }
    state.countrysideRouteTemplateFormMode = "add";
    state.countrysideRouteTemplateEditingScheduleId = "";
    state.countrysideRouteTemplateMoveTargetRouteGroupId = "";
    state.countrysideRouteTemplateForm = createEmptyRouteTemplateForm();
    state.countrysideRouteManagementError = "";
    resetRouteGroupForm();
    renderBoard();
  }

  function startCreatePickupFromRouteTemplate(template) {
    state.activeCountrysideRouteTemplateDetailId = "";
    state.countrysideOpShopPickupFormMode = "add";
    state.countrysideOpShopPickupEditingTaskId = "";
    state.countrysideOpShopPickupForm = {
      route_group_id: template.route_group_id || state.selectedCountrysideRouteGroupId || "",
      schedule_id: template.schedule_id,
      pickup_date: "",
      assigned_driver_id: template.default_driver_id || "",
      notes: "",
    };
    state.countrysideOpShopPickupListError = "";
    state.countrysideRouteManagementError = "";
    resetRouteGroupForm();
    resetRouteTemplateForm();
    renderBoard();
  }

  function startMoveRouteTemplate(template) {
    state.activeCountrysideRouteTemplateDetailId = "";
    state.countrysideRouteTemplateFormMode = "move";
    state.countrysideRouteTemplateEditingScheduleId = template.schedule_id;
    state.countrysideRouteTemplateMoveTargetRouteGroupId = "";
    state.countrysideRouteTemplateForm = {
      name: template.name,
      route_group_id: template.route_group_id,
    };
    state.countrysideRouteManagementError = "";
    resetRouteGroupForm();
    renderBoard();
  }

  function startRemoveRouteTemplate(template) {
    state.activeCountrysideRouteTemplateDetailId = "";
    state.countrysideRouteTemplateFormMode = "remove";
    state.countrysideRouteTemplateEditingScheduleId = template.schedule_id;
    state.countrysideRouteTemplateMoveTargetRouteGroupId = "";
    state.countrysideRouteTemplateForm = {
      name: template.name,
      route_group_id: template.route_group_id,
    };
    state.countrysideRouteManagementError = "";
    resetRouteGroupForm();
    renderBoard();
  }

  function cancelRouteTemplateForm() {
    resetRouteTemplateForm();
    state.countrysideRouteManagementError = "";
    renderBoard();
  }

  function openRouteTemplateDetail(template) {
    state.activeCountrysideRouteTemplateDetailId = template.schedule_id;
    renderBoard();
  }

  function closeRouteTemplateDetail() {
    state.activeCountrysideRouteTemplateDetailId = "";
    renderBoard();
  }

  function updateRouteTemplateForm(field, value) {
    if (field === "target_route_group_id") {
      state.countrysideRouteTemplateMoveTargetRouteGroupId = value;
      renderBoard();
      return;
    }
    state.countrysideRouteTemplateForm = {
      ...state.countrysideRouteTemplateForm,
      [field]: value,
    };
  }

  async function handleAddRouteTemplate() {
    if (state.isCountrysideRouteTemplateSaving || !state.selectedCountrysideRouteGroupId) {
      return;
    }
    state.isCountrysideRouteTemplateSaving = true;
    state.countrysideRouteManagementError = "";
    renderBoard();

    try {
      await apiAddCountrysideRouteMembership(
        state.selectedCountrysideRouteGroupId,
        normalizeRouteTemplateForm(),
      );
      resetRouteTemplateForm();
      await refreshCountrysideRouteData();
    } catch (error) {
      state.countrysideRouteManagementError = `Unable to add OP SHOP to this route. ${error.message}`;
    } finally {
      state.isCountrysideRouteTemplateSaving = false;
      renderBoard();
    }
  }

  async function handleMoveRouteTemplate() {
    if (
      state.isCountrysideRouteTemplateSaving ||
      !state.countrysideRouteTemplateEditingScheduleId ||
      !state.countrysideRouteTemplateMoveTargetRouteGroupId
    ) {
      return;
    }
    state.isCountrysideRouteTemplateSaving = true;
    state.countrysideRouteManagementError = "";
    renderBoard();

    try {
      await apiMoveCountrysideRouteMembership(
        state.countrysideRouteTemplateEditingScheduleId,
        {
          target_route_group_id: state.countrysideRouteTemplateMoveTargetRouteGroupId,
        },
      );
      resetRouteTemplateForm();
      await refreshCountrysideRouteData();
    } catch (error) {
      state.countrysideRouteManagementError = `Unable to move Countryside route template. ${error.message}`;
    } finally {
      state.isCountrysideRouteTemplateSaving = false;
      renderBoard();
    }
  }

  async function handleRemoveRouteTemplate() {
    if (
      state.isCountrysideRouteTemplateSaving ||
      !state.countrysideRouteTemplateEditingScheduleId
    ) {
      return;
    }
    state.isCountrysideRouteTemplateSaving = true;
    state.countrysideRouteManagementError = "";
    renderBoard();

    try {
      await apiRemoveCountrysideRouteMembership(
        state.countrysideRouteTemplateEditingScheduleId,
      );
      resetRouteTemplateForm();
      await refreshCountrysideRouteData();
    } catch (error) {
      state.countrysideRouteManagementError = `Unable to remove OP SHOP from this route. ${error.message}`;
    } finally {
      state.isCountrysideRouteTemplateSaving = false;
      renderBoard();
    }
  }

  function updatePickupTaskForm(field, value) {
    const shouldRender =
      field === "route_group_id" ||
      field === "pickup_date" ||
      field === "assigned_driver_id";
    const nextForm = {
      ...state.countrysideOpShopPickupForm,
      [field]: value,
    };
    if (field === "route_group_id") {
      nextForm.assigned_driver_id = "";
    }
    state.countrysideOpShopPickupForm = nextForm;
    if (shouldRender) {
      renderBoard();
    }
  }

  async function handleCreatePickupTask() {
    if (state.isCountrysideOpShopPickupSaving) {
      return;
    }

    state.isCountrysideOpShopPickupSaving = true;
    state.countrysideOpShopPickupListError = "";
    renderBoard();

    try {
      const routeGroupId =
        state.countrysideOpShopPickupForm.route_group_id ||
        state.selectedCountrysideRouteGroupId ||
        "";
      const selectedDriverId = state.countrysideOpShopPickupForm.assigned_driver_id || "";
      await apiAssignCountrysideRouteGroup(routeGroupId, {
        dispatch_date: state.dispatchDate,
        pickup_date: state.countrysideOpShopPickupForm.pickup_date,
        assigned_driver_id: selectedDriverId,
        notes: state.countrysideOpShopPickupForm.notes || null,
      });
      state.countrysideOpShopPickupFormMode = "";
      state.countrysideOpShopPickupForm = {};
      await loadBoard(state.dispatchDate, { force: true });
      initializeAssignedDriverSelections();
    } catch (error) {
      state.countrysideOpShopPickupListError = `Unable to assign Countryside route group. ${error.message}`;
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
        dispatch_date: state.dispatchDate,
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

  async function setSelectedRouteGroup(routeGroupId) {
    const scrollSnapshot = captureElementScroll("#opshop-countryside-pickup-list-root");
    state.selectedCountrysideRouteGroupId = routeGroupId || "";
    resetRouteGroupForm();
    resetRouteTemplateForm();
    renderBoard();
    await loadRouteMemberships();
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

  async function refreshCountrysideRouteData() {
    await Promise.all([loadRouteGroups(), loadScheduleCandidates(), loadRouteMemberships()]);
    await loadBoard(state.dispatchDate, { force: true });
    initializeAssignedDriverSelections();
  }

  function getSelectedRouteGroup() {
    return state.countrysideRouteGroups.find(
      (routeGroup) => routeGroup.route_group_id === state.selectedCountrysideRouteGroupId,
    );
  }

  function resetRouteGroupForm() {
    state.isCountrysideRouteFormOpen = false;
    state.countrysideRouteFormMode = "";
    state.countrysideRouteForm = {};
  }

  function resetRouteTemplateForm() {
    state.countrysideRouteTemplateFormMode = "";
    state.countrysideRouteTemplateForm = {};
    state.countrysideRouteTemplateEditingScheduleId = "";
    state.countrysideRouteTemplateMoveTargetRouteGroupId = "";
    state.activeCountrysideRouteTemplateDetailId = "";
  }

  function createEmptyRouteTemplateForm() {
    return {
      name: "",
      suburb: "",
      street_address: "",
      area_region: "",
      primary_contact: "",
      primary_phone: "",
      secondary_contact: "",
      secondary_phone: "",
      pickup_frequency: "On Call",
      time_window: "",
      access_type: "",
      key_required: false,
      trailer_restriction: "",
      status_notes: "",
      default_driver_id: "",
    };
  }

  function normalizeRouteTemplateForm() {
    return {
      ...state.countrysideRouteTemplateForm,
      key_required: Boolean(state.countrysideRouteTemplateForm.key_required),
      call_before_arrival: false,
    };
  }

  return {
    cancelPickupTaskForm,
    cancelRouteGroupForm,
    cancelRouteTemplateForm,
    closeCountrysideOpShopPickupList,
    handleAddRouteTemplate,
    handleCreatePickupTask,
    handleCreateRouteGroup,
    handleDeletePickupTask,
    handleDisableRouteGroup,
    handleMoveRouteTemplate,
    handleRemoveRouteTemplate,
    handleRenameRouteGroup,
    handleUpdatePickupTask,
    loadRouteGroups,
    loadRouteMemberships,
    loadScheduleCandidates,
    closeRouteTemplateDetail,
    openRouteTemplateDetail,
    openCountrysideOpShopPickupList,
    setSelectedRouteGroup,
    startAddPickupTask,
    startAddRouteTemplate,
    startCreatePickupFromRouteTemplate,
    startDeletePickupTask,
    startDisableRouteGroup,
    startEditPickupTask,
    startMoveRouteTemplate,
    startNewRouteGroup,
    startRemoveRouteTemplate,
    startRenameRouteGroup,
    updateAssignedDriverSelection,
    updatePickupTaskForm,
    updateRouteGroupForm,
    updateRouteTemplateForm,
  };
}
