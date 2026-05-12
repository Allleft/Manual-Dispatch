import {
  apiCreateDriver,
  apiCreateVehicle,
  apiDeleteDriver,
  apiDeleteVehicle,
  apiGetSpecifications,
  apiUpdateDriver,
  apiUpdateVehicle,
} from "../api/manual-dispatch-api.js";

function getDefaultDriverSpecificationForm(driver = {}) {
  return {
    name: driver.name || "",
    license_no: driver.license_no || "",
    email: driver.email || "",
    phone_number: driver.phone_number || "",
    start_time: driver.start_time || "",
    end_time: driver.end_time || "",
    is_available: driver.is_available !== false,
    pallet_only: Boolean(driver.pallet_only),
    preferred_zone: driver.preferred_zone || "",
  };
}

function getDefaultVehicleSpecificationForm(vehicle = {}) {
  return {
    rego: vehicle.rego || "",
    type: vehicle.type || "",
    is_available: vehicle.is_available !== false,
    pallet_capacity: String(vehicle.pallet_capacity ?? 0),
    tub_capacity: String(vehicle.tub_capacity ?? 0),
    trolley_capacity: String(vehicle.trolley_capacity ?? 0),
    stillage_capacity: String(vehicle.stillage_capacity ?? 0),
  };
}

function getDriverSpecificationPayload(form) {
  return {
    ...form,
    is_available: Boolean(form.is_available),
    pallet_only: Boolean(form.pallet_only),
  };
}

function getVehicleSpecificationPayload(form) {
  return {
    ...form,
    is_available: Boolean(form.is_available),
    pallet_capacity: Number(form.pallet_capacity || 0),
    tub_capacity: Number(form.tub_capacity || 0),
    trolley_capacity: Number(form.trolley_capacity || 0),
    stillage_capacity: Number(form.stillage_capacity || 0),
  };
}

export function createSpecificationActions({
  loadBoard,
  renderSpecificationPanel,
  renderSpecificationShell,
  state,
  updateSpecificationTabButtons,
}) {
  function showSpecificationError(message) {
    state.specificationError = message;
    const errorElement = document.querySelector("#specification-error");
    if (errorElement) {
      errorElement.hidden = !message;
      errorElement.textContent = message || "";
    }
  }

  function clearSpecificationError() {
    showSpecificationError("");
  }

  async function loadSpecificationsIntoState() {
    state.specificationLoading = true;
    clearSpecificationError();

    try {
      const payload = await apiGetSpecifications();
      state.specificationDrivers = payload.drivers || [];
      state.specificationVehicles = payload.vehicles || [];
    } catch (error) {
      showSpecificationError(`Unable to load specifications. ${error.message}`);
    } finally {
      state.specificationLoading = false;
    }
  }

  async function openSpecificationModal() {
    state.isSpecificationModalOpen = true;
    state.specificationError = "";
    state.specificationDirty = false;
    state.specificationLoading = false;
    state.driverSpecificationForm = null;
    state.driverSpecificationEditingId = "";
    state.vehicleSpecificationForm = null;
    state.vehicleSpecificationEditingId = "";
    renderSpecificationShell();
    renderSpecificationPanel();
    await loadSpecificationsIntoState();
    renderSpecificationPanel();
  }

  async function closeSpecificationModal() {
    const shouldReloadBoard = state.specificationDirty;
    const root = document.querySelector("#specification-root");
    state.isSpecificationModalOpen = false;
    state.specificationError = "";
    state.specificationDirty = false;
    state.specificationLoading = false;
    state.specificationSaving = false;
    state.driverSpecificationForm = null;
    state.driverSpecificationEditingId = "";
    state.vehicleSpecificationForm = null;
    state.vehicleSpecificationEditingId = "";
    if (root) {
      root.innerHTML = "";
    }

    if (shouldReloadBoard) {
      await loadBoard(state.dispatchDate, { force: true });
    }
  }

  function startAddDriverSpecification() {
    state.specificationActiveTab = "drivers";
    state.driverSpecificationEditingId = "";
    state.driverSpecificationForm = getDefaultDriverSpecificationForm();
    updateSpecificationTabButtons();
    renderSpecificationPanel({ preserveScroll: true });
  }

  function startEditDriverSpecification(driver) {
    state.specificationActiveTab = "drivers";
    state.driverSpecificationEditingId = driver.driver_id;
    state.driverSpecificationForm = getDefaultDriverSpecificationForm(driver);
    updateSpecificationTabButtons();
    renderSpecificationPanel({ preserveScroll: true });
  }

  function cancelDriverSpecificationForm() {
    state.driverSpecificationEditingId = "";
    state.driverSpecificationForm = null;
    renderSpecificationPanel({ preserveScroll: true });
  }

  function updateDriverSpecificationForm(field, value) {
    state.driverSpecificationForm = {
      ...state.driverSpecificationForm,
      [field]: value,
    };
  }

  function startAddVehicleSpecification() {
    state.specificationActiveTab = "vehicles";
    state.vehicleSpecificationEditingId = "";
    state.vehicleSpecificationForm = getDefaultVehicleSpecificationForm();
    updateSpecificationTabButtons();
    renderSpecificationPanel({ preserveScroll: true });
  }

  function startEditVehicleSpecification(vehicle) {
    state.specificationActiveTab = "vehicles";
    state.vehicleSpecificationEditingId = vehicle.vehicle_id;
    state.vehicleSpecificationForm = getDefaultVehicleSpecificationForm(vehicle);
    updateSpecificationTabButtons();
    renderSpecificationPanel({ preserveScroll: true });
  }

  function cancelVehicleSpecificationForm() {
    state.vehicleSpecificationEditingId = "";
    state.vehicleSpecificationForm = null;
    renderSpecificationPanel({ preserveScroll: true });
  }

  function updateVehicleSpecificationForm(field, value) {
    state.vehicleSpecificationForm = {
      ...state.vehicleSpecificationForm,
      [field]: value,
    };
  }

  function updateSpecificationDriverLocal(driverId, updates) {
    state.specificationDrivers = state.specificationDrivers.map((driver) =>
      driver.driver_id === driverId ? { ...driver, ...updates } : driver,
    );
  }

  function updateSpecificationVehicleLocal(vehicleId, updates) {
    state.specificationVehicles = state.specificationVehicles.map((vehicle) =>
      vehicle.vehicle_id === vehicleId ? { ...vehicle, ...updates } : vehicle,
    );
  }

  async function refreshSpecificationsOnly({ markDirty = true } = {}) {
    if (markDirty) {
      state.specificationDirty = true;
    }
    await loadSpecificationsIntoState();
    renderSpecificationPanel({ preserveScroll: true });
  }

  async function handleSaveDriverSpecification() {
    if (state.specificationSaving || !state.driverSpecificationForm) {
      return;
    }

    state.specificationSaving = true;
    state.specificationError = "";
    renderSpecificationPanel({ preserveScroll: true });

    try {
      const payload = getDriverSpecificationPayload(state.driverSpecificationForm);
      if (state.driverSpecificationEditingId) {
        await apiUpdateDriver(state.driverSpecificationEditingId, payload);
      } else {
        await apiCreateDriver(payload);
      }
      state.driverSpecificationEditingId = "";
      state.driverSpecificationForm = null;
      await refreshSpecificationsOnly();
    } catch (error) {
      state.specificationError = `Unable to save Driver. ${error.message}`;
      showSpecificationError(state.specificationError);
    } finally {
      state.specificationSaving = false;
      renderSpecificationPanel({ preserveScroll: true });
    }
  }

  async function handleToggleDriverAvailability(driver, isAvailable, checkbox) {
    const previousValue = driver.is_available !== false;
    clearSpecificationError();
    if (checkbox) {
      checkbox.disabled = true;
    }

    try {
      await apiUpdateDriver(driver.driver_id, {
        ...getDefaultDriverSpecificationForm(driver),
        is_available: isAvailable,
      });

      updateSpecificationDriverLocal(driver.driver_id, { is_available: isAvailable });
      driver.is_available = isAvailable;
      state.specificationDirty = true;
    } catch (error) {
      updateSpecificationDriverLocal(driver.driver_id, { is_available: previousValue });
      driver.is_available = previousValue;

      if (checkbox) {
        checkbox.checked = previousValue;
      }

      showSpecificationError(`Unable to update Driver availability. ${error.message}`);
    } finally {
      if (checkbox) {
        checkbox.disabled = false;
      }
    }
  }

  async function handleDeleteDriverSpecification(driverId) {
    const confirmed = window.confirm("Are you sure you want to delete this driver?");
    if (!confirmed) {
      return;
    }

    state.specificationSaving = true;
    state.specificationError = "";
    renderSpecificationPanel({ preserveScroll: true });

    try {
      await apiDeleteDriver(driverId);
      await refreshSpecificationsOnly();
    } catch (error) {
      state.specificationError = `Unable to delete Driver. ${error.message}`;
      showSpecificationError(state.specificationError);
    } finally {
      state.specificationSaving = false;
      renderSpecificationPanel({ preserveScroll: true });
    }
  }

  async function handleSaveVehicleSpecification() {
    if (state.specificationSaving || !state.vehicleSpecificationForm) {
      return;
    }

    state.specificationSaving = true;
    state.specificationError = "";
    renderSpecificationPanel({ preserveScroll: true });

    try {
      const payload = getVehicleSpecificationPayload(state.vehicleSpecificationForm);
      if (state.vehicleSpecificationEditingId) {
        await apiUpdateVehicle(state.vehicleSpecificationEditingId, payload);
      } else {
        await apiCreateVehicle(payload);
      }
      state.vehicleSpecificationEditingId = "";
      state.vehicleSpecificationForm = null;
      await refreshSpecificationsOnly();
    } catch (error) {
      state.specificationError = `Unable to save Vehicle. ${error.message}`;
      showSpecificationError(state.specificationError);
    } finally {
      state.specificationSaving = false;
      renderSpecificationPanel({ preserveScroll: true });
    }
  }

  async function handleToggleVehicleAvailability(vehicle, isAvailable, checkbox) {
    const previousValue = vehicle.is_available !== false;
    clearSpecificationError();
    if (checkbox) {
      checkbox.disabled = true;
    }

    try {
      await apiUpdateVehicle(vehicle.vehicle_id, {
        ...getDefaultVehicleSpecificationForm(vehicle),
        is_available: isAvailable,
      });

      updateSpecificationVehicleLocal(vehicle.vehicle_id, { is_available: isAvailable });
      vehicle.is_available = isAvailable;
      state.specificationDirty = true;
    } catch (error) {
      updateSpecificationVehicleLocal(vehicle.vehicle_id, { is_available: previousValue });
      vehicle.is_available = previousValue;

      if (checkbox) {
        checkbox.checked = previousValue;
      }

      showSpecificationError(`Unable to update Vehicle availability. ${error.message}`);
    } finally {
      if (checkbox) {
        checkbox.disabled = false;
      }
    }
  }

  async function handleDeleteVehicleSpecification(vehicleId) {
    const confirmed = window.confirm("Are you sure you want to delete this vehicle?");
    if (!confirmed) {
      return;
    }

    state.specificationSaving = true;
    state.specificationError = "";
    renderSpecificationPanel({ preserveScroll: true });

    try {
      await apiDeleteVehicle(vehicleId);
      await refreshSpecificationsOnly();
    } catch (error) {
      state.specificationError = `Unable to delete Vehicle. ${error.message}`;
      showSpecificationError(state.specificationError);
    } finally {
      state.specificationSaving = false;
      renderSpecificationPanel({ preserveScroll: true });
    }
  }

  return {
    cancelDriverSpecificationForm,
    cancelVehicleSpecificationForm,
    closeSpecificationModal,
    handleDeleteDriverSpecification,
    handleDeleteVehicleSpecification,
    handleSaveDriverSpecification,
    handleSaveVehicleSpecification,
    handleToggleDriverAvailability,
    handleToggleVehicleAvailability,
    openSpecificationModal,
    showSpecificationError,
    startAddDriverSpecification,
    startAddVehicleSpecification,
    startEditDriverSpecification,
    startEditVehicleSpecification,
    updateDriverSpecificationForm,
    updateVehicleSpecificationForm,
  };
}
