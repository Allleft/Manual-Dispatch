import {
  apiApplyOncallOpShopPickupAssignments,
  apiCreateOncallOpShopPickup,
  apiDeleteOpShopPickup,
  apiListOncallOpShopPickupSchedules,
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
    resetTemplatePicker();
    initializeAssignedDriverSelections();
    initializeCollapsedDateGroups();
    renderBoard();
    await loadScheduleCandidates();
  }

  async function closeOncallOpShopPickupList() {
    if (state.isOncallOpShopPickupSaving || state.isOncallOpShopPickupListLoading) {
      return;
    }
    state.isOncallOpShopPickupSaving = true;
    state.oncallOpShopPickupListError = "";
    renderBoard();

    try {
      await apiApplyOncallOpShopPickupAssignments({
        dispatch_date: state.dispatchDate,
        assignments: state.oncallOpShopPickups
          .filter((pickup) => !isGeneratedTask("OPSHOP_PICKUP", pickup.pickup_task_id))
          .map((pickup) => ({
            pickup_task_id: pickup.pickup_task_id,
            driver_id: state.oncallOpShopPickupAssignedDriverSelections[pickup.pickup_task_id] || "",
          })),
      });
      state.isOncallOpShopPickupListOpen = false;
      state.oncallOpShopPickupFormMode = "";
      state.oncallOpShopPickupEditingTaskId = "";
      state.oncallOpShopPickupForm = {};
      resetTemplatePicker();
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
    resetTemplatePicker();
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
    resetTemplatePicker();
    state.oncallOpShopPickupListError = "";
    renderBoard();
  }

  function updateOncallTemplateFilter(value) {
    const activeElement = document.activeElement;
    const shouldRestoreFocus =
      activeElement && activeElement.dataset.role === "oncall-template-filter";
    const selectionStart = shouldRestoreFocus ? activeElement.selectionStart : null;
    const selectionEnd = shouldRestoreFocus ? activeElement.selectionEnd : null;
    const nextFilter = value || "";
    const currentScheduleId = state.oncallOpShopPickupForm.schedule_id || "";
    const selectedCandidate = state.oncallOpShopPickupScheduleCandidates.find(
      (item) => item.schedule_id === currentScheduleId,
    );
    const selectedCandidateText = getOncallTemplateDisplayText(selectedCandidate);

    state.oncallOpShopPickupTemplateFilter = nextFilter;
    state.isOncallOpShopPickupTemplatePickerOpen = true;
    if (
      currentScheduleId &&
      normalizeTemplateSearchText(nextFilter) !== normalizeTemplateSearchText(selectedCandidateText)
    ) {
      state.oncallOpShopPickupForm = {
        ...state.oncallOpShopPickupForm,
        schedule_id: "",
      };
    }
    renderBoard();
    restoreTemplateFilterFocus(shouldRestoreFocus, selectionStart, selectionEnd);
  }

  function selectOncallPickupTemplate(scheduleId) {
    const candidate = state.oncallOpShopPickupScheduleCandidates.find(
      (item) => item.schedule_id === scheduleId,
    );
    state.oncallOpShopPickupForm = {
      ...state.oncallOpShopPickupForm,
      schedule_id: candidate ? candidate.schedule_id : "",
      pickup_date: getDefaultPickupDateForCandidate(candidate),
      assigned_driver_id: candidate ? candidate.default_driver_id || "" : "",
    };
    state.oncallOpShopPickupTemplateFilter = getOncallTemplateDisplayText(candidate);
    state.isOncallOpShopPickupTemplatePickerOpen = false;
    renderBoard();
  }

  function setOncallTemplatePickerOpen(isOpen) {
    const nextOpen = Boolean(isOpen);
    if (state.isOncallOpShopPickupTemplatePickerOpen === nextOpen) {
      return;
    }
    const activeElement = document.activeElement;
    const shouldRestoreFocus =
      activeElement && activeElement.dataset.role === "oncall-template-filter";
    const selectionStart = shouldRestoreFocus ? activeElement.selectionStart : null;
    const selectionEnd = shouldRestoreFocus ? activeElement.selectionEnd : null;
    state.isOncallOpShopPickupTemplatePickerOpen = nextOpen;
    renderBoard();
    restoreTemplateFilterFocus(shouldRestoreFocus, selectionStart, selectionEnd);
  }

  function updatePickupTaskForm(field, value) {
    const shouldRender = ["schedule_id", "pickup_date"].includes(field);
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
    if (shouldRender) {
      renderBoard();
    }
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
        dispatch_date: state.dispatchDate,
        assigned_driver_id: selectedDriverId || null,
        notes: state.oncallOpShopPickupForm.notes || null,
      });
      state.oncallOpShopPickupFormMode = "";
      state.oncallOpShopPickupForm = {};
      resetTemplatePicker();
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
        dispatch_date: state.dispatchDate,
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

  function toggleDateGroup(pickupDate) {
    const scrollSnapshot = captureElementScroll("#opshop-oncall-pickup-list-root");

    state.collapsedOncallOpShopPickupDates = toggleCollapsedPickupDateGroup(
      state.collapsedOncallOpShopPickupDates,
      pickupDate,
      state.dispatchDate,
    );
    renderBoard();
    restoreElementScroll(scrollSnapshot);
  }

  function resetTemplatePicker() {
    state.oncallOpShopPickupTemplateFilter = "";
    state.isOncallOpShopPickupTemplatePickerOpen = false;
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

  function initializeCollapsedDateGroups() {
    state.collapsedOncallOpShopPickupDates = initializeCollapsedPickupDateGroups(
      state.oncallOpShopPickups,
      state.dispatchDate,
    );
  }

  function getDefaultPickupDateForCandidate(candidate) {
    if (!candidate || !candidate.run_day || !(candidate.run_day in WEEKDAY_OFFSETS)) {
      return state.dispatchDate || "";
    }
    const monday = getOncallTargetWeekMonday(state.dispatchDate);
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
    selectOncallPickupTemplate,
    setOncallTemplatePickerOpen,
    startAddPickupTask,
    startDeletePickupTask,
    startEditPickupTask,
    toggleDateGroup,
    updateAssignedDriverSelection,
    updateOncallTemplateFilter,
    updatePickupTaskForm,
  };
}

function getOncallTemplateDisplayText(candidate) {
  if (!candidate) {
    return "";
  }
  return [
    candidate.opshop_name,
    candidate.suburb,
    candidate.run_day || "Gavin",
    candidate.default_driver_name || candidate.default_driver_alias,
  ]
    .filter(Boolean)
    .join(" - ");
}

function candidateMatchesTemplateFilter(candidate, filterText) {
  const filter = normalizeTemplateSearchText(filterText);
  if (!filter) {
    return true;
  }
  if (!candidate) {
    return false;
  }
  return [
    candidate.opshop_name,
    candidate.suburb,
    candidate.street_address,
  ].some((value) => normalizeTemplateSearchText(value).includes(filter));
}

function normalizeTemplateSearchText(value) {
  return String(value || "").trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function restoreTemplateFilterFocus(shouldRestoreFocus, selectionStart, selectionEnd) {
  if (!shouldRestoreFocus) {
    return;
  }
  requestAnimationFrame(() => {
    const input = document.querySelector('[data-role="oncall-template-filter"]');
    if (!input) {
      return;
    }
    input.focus();
    if (
      Number.isInteger(selectionStart) &&
      Number.isInteger(selectionEnd) &&
      typeof input.setSelectionRange === "function"
    ) {
      input.setSelectionRange(selectionStart, selectionEnd);
    }
  });
}

function getOncallTargetWeekMonday(dispatchDateValue) {
  const dispatchDate = parseLocalDate(dispatchDateValue);
  if (!dispatchDate) {
    return null;
  }
  const monday = new Date(dispatchDate);
  monday.setDate(dispatchDate.getDate() - ((dispatchDate.getDay() + 6) % 7));
  if (dispatchDate.getDay() === 5 || dispatchDate.getDay() === 6 || dispatchDate.getDay() === 0) {
    monday.setDate(monday.getDate() + 7);
  }
  return monday;
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
