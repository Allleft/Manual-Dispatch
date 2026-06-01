import {
  apiCreateOpShopTemplate,
  apiDisableOpShopTemplate,
  apiListOpShopTemplates,
  apiUpdateOpShopTemplate,
} from "../api/manual-dispatch-api.js";


function emptyTemplateForm(runType) {
  return {
    run_type: runType,
    run_day: runType === "REGULAR" ? "MONDAY" : "",
    name: "",
    suburb: "",
    street_address: "",
    area_region: "",
    primary_contact: "",
    primary_phone: "",
    secondary_contact: "",
    secondary_phone: "",
    pickup_frequency: runType === "ON_CALL" ? "On Call" : "Weekly",
    time_window: "",
    call_before_arrival: false,
    call_timing: "",
    access_type: "",
    key_required: false,
    trailer_restriction: "",
    status_notes: "",
    default_driver_id: "",
  };
}


function templateToForm(template) {
  return {
    run_type: template.run_type,
    run_day: template.run_day || "",
    name: template.name || "",
    suburb: template.suburb || "",
    street_address: template.street_address || "",
    area_region: template.area_region || "",
    primary_contact: template.primary_contact || "",
    primary_phone: template.primary_phone || "",
    secondary_contact: template.secondary_contact || "",
    secondary_phone: template.secondary_phone || "",
    pickup_frequency: template.pickup_frequency || "",
    time_window: template.time_window || "",
    call_before_arrival: Boolean(template.call_before_arrival),
    call_timing: template.call_timing || "",
    access_type: template.access_type || "",
    key_required: Boolean(template.key_required),
    trailer_restriction: template.trailer_restriction || "",
    status_notes: template.status_notes || "",
    default_driver_id: template.default_driver_id || "",
  };
}


export function createOpShopTemplateActions({
  loadBoard,
  reloadCountrysideCandidates,
  reloadOncallCandidates,
  reloadRegularCandidates,
  renderBoard,
  state,
}) {
  async function openTemplateManagement() {
    state.isOpShopTemplateManagementOpen = true;
    state.opshopTemplateError = "";
    state.opshopTemplateFormMode = "";
    state.opshopTemplateEditingScheduleId = "";
    state.opshopTemplateForm = {};
    renderBoard();
    await loadTemplates();
  }

  function closeTemplateManagement() {
    if (state.isOpShopTemplateSaving) {
      return;
    }
    state.isOpShopTemplateManagementOpen = false;
    state.opshopTemplateFormMode = "";
    state.opshopTemplateEditingScheduleId = "";
    state.opshopTemplateError = "";
    renderBoard();
  }

  async function loadTemplates() {
    state.isOpShopTemplateLoading = true;
    state.opshopTemplateError = "";
    renderBoard();
    try {
      state.opshopTemplates = await apiListOpShopTemplates(
        state.opshopTemplateActiveTab,
        state.opshopTemplateIncludeInactive,
      );
    } catch (error) {
      state.opshopTemplateError = `Unable to load OP SHOP templates. ${error.message}`;
    } finally {
      state.isOpShopTemplateLoading = false;
      renderBoard();
    }
  }

  async function selectTab(runType) {
    state.opshopTemplateActiveTab = runType;
    state.opshopTemplateFormMode = "";
    state.opshopTemplateEditingScheduleId = "";
    state.opshopTemplateForm = {};
    await loadTemplates();
  }

  async function toggleIncludeInactive(checked) {
    state.opshopTemplateIncludeInactive = checked;
    await loadTemplates();
  }

  function startAddTemplate() {
    state.opshopTemplateFormMode = "add";
    state.opshopTemplateEditingScheduleId = "";
    state.opshopTemplateForm = emptyTemplateForm(state.opshopTemplateActiveTab);
    state.opshopTemplateError = "";
    renderBoard();
  }

  function startEditTemplate(template) {
    state.opshopTemplateFormMode = "edit";
    state.opshopTemplateEditingScheduleId = template.schedule_id;
    state.opshopTemplateForm = templateToForm(template);
    state.opshopTemplateError = "";
    renderBoard();
  }

  function startDisableTemplate(template) {
    state.opshopTemplateFormMode = "disable";
    state.opshopTemplateEditingScheduleId = template.schedule_id;
    state.opshopTemplateError = "";
    renderBoard();
  }

  function cancelTemplateForm() {
    state.opshopTemplateFormMode = "";
    state.opshopTemplateEditingScheduleId = "";
    state.opshopTemplateForm = {};
    state.opshopTemplateError = "";
    renderBoard();
  }

  function updateTemplateForm(field, value, options = {}) {
    const form = {
      ...state.opshopTemplateForm,
      [field]: value,
    };
    if (field === "run_type") {
      form.run_day = value === "REGULAR" ? form.run_day || "MONDAY" : form.run_day;
      form.pickup_frequency = value === "ON_CALL" && !form.pickup_frequency
        ? "On Call"
        : form.pickup_frequency;
    }
    state.opshopTemplateForm = form;
    const shouldRender = options.render ?? field === "run_type";
    if (shouldRender) {
      renderBoard();
    }
  }

  async function saveTemplate() {
    if (state.isOpShopTemplateSaving) {
      return;
    }
    state.isOpShopTemplateSaving = true;
    state.opshopTemplateError = "";
    renderBoard();
    try {
      if (state.opshopTemplateFormMode === "edit") {
        await apiUpdateOpShopTemplate(
          state.opshopTemplateEditingScheduleId,
          state.opshopTemplateForm,
        );
      } else {
        await apiCreateOpShopTemplate(state.opshopTemplateForm);
      }
      state.opshopTemplateActiveTab = state.opshopTemplateForm.run_type;
      state.opshopTemplateFormMode = "";
      state.opshopTemplateEditingScheduleId = "";
      state.opshopTemplateForm = {};
      await refreshTemplateConsumers();
    } catch (error) {
      state.opshopTemplateError = `Unable to save OP SHOP template. ${error.message}`;
    } finally {
      state.isOpShopTemplateSaving = false;
      renderBoard();
    }
  }

  async function disableTemplate() {
    if (state.isOpShopTemplateSaving || !state.opshopTemplateEditingScheduleId) {
      return;
    }
    state.isOpShopTemplateSaving = true;
    state.opshopTemplateError = "";
    renderBoard();
    try {
      await apiDisableOpShopTemplate(state.opshopTemplateEditingScheduleId);
      state.opshopTemplateFormMode = "";
      state.opshopTemplateEditingScheduleId = "";
      await refreshTemplateConsumers();
    } catch (error) {
      state.opshopTemplateError = `Unable to disable OP SHOP template. ${error.message}`;
    } finally {
      state.isOpShopTemplateSaving = false;
      renderBoard();
    }
  }

  async function refreshTemplateConsumers() {
    await loadTemplates();
    if (state.isOpShopPickupListOpen) {
      await reloadRegularCandidates();
    }
    if (state.isOncallOpShopPickupListOpen) {
      await reloadOncallCandidates();
    }
    if (state.isCountrysideOpShopPickupListOpen && reloadCountrysideCandidates) {
      await reloadCountrysideCandidates();
    }
    await loadBoard(state.dispatchDate, { force: true });
  }

  return {
    cancelTemplateForm,
    closeTemplateManagement,
    disableTemplate,
    loadTemplates,
    openTemplateManagement,
    saveTemplate,
    selectTab,
    startAddTemplate,
    startDisableTemplate,
    startEditTemplate,
    toggleIncludeInactive,
    updateTemplateForm,
  };
}
