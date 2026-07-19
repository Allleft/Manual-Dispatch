export function createDeliverySpecificationActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const handleWorkspaceMigrationGuard = (...args) => context.actions.handleWorkspaceMigrationGuard(...args);
  const loadDeliveryRoute = (...args) => context.actions.loadDeliveryRoute(...args);
  const runDeliveryAction = (...args) => context.actions.runDeliveryAction(...args);
  const captureMutationContext = (...args) => context.actions.captureMutationContext(...args);
  const isDeliveryMutationCurrent = (...args) => context.actions.isDeliveryMutationCurrent(...args);

  async function openDeliverySpecifications() {
    context.deliverySpecificationRequestVersion += 1;
    state.deliverySpecificationModalOpen = true;
    state.deliverySpecificationError = "";
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    renderWorkspace();
    await refreshDeliverySpecifications();
  }

  function closeDeliverySpecifications() {
    context.deliverySpecificationRequestVersion += 1;
    state.deliverySpecificationModalOpen = false;
    state.deliverySpecificationError = "";
    state.deliverySpecificationBusyKey = "";
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    renderWorkspace();
  }

  function setDeliverySpecificationTab(tab) {
    state.deliverySpecificationTab = tab === "vehicles" ? "vehicles" : "drivers";
    state.deliverySpecificationError = "";
    renderWorkspace();
  }

  async function refreshDeliverySpecifications() {
    const context = captureMutationContext();
    const requestVersion = context.deliverySpecificationRequestVersion;
    const isCurrent = () =>
      isDeliveryMutationCurrent(context) &&
      state.workspaceRoute === "delivery/task-pool" &&
      state.deliverySpecificationModalOpen &&
      requestVersion === context.deliverySpecificationRequestVersion;
    try {
      const specifications = await api.getDeliverySpecifications();
      if (!isCurrent()) {
        return;
      }
      state.deliverySpecifications = specifications;
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isCurrent()) {
        state.deliverySpecificationError =
          `Unable to load Delivery specifications. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        renderWorkspace();
      }
    }
  }

  function startAddDeliveryDriver() {
    state.deliverySpecificationTab = "drivers";
    state.deliveryDriverEditingId = "";
    state.deliveryDriverForm = defaultDeliveryDriverForm();
    state.deliverySpecificationError = "";
    renderWorkspace();
  }

  function startEditDeliveryDriver(driverId) {
    const driver = (state.deliverySpecifications?.drivers || state.deliveryBoard?.drivers || [])
      .find((item) => item.driver_id === driverId);
    state.deliverySpecificationTab = "drivers";
    state.deliveryDriverEditingId = driverId;
    state.deliveryDriverForm = defaultDeliveryDriverForm(driver || {});
    state.deliverySpecificationError = "";
    renderWorkspace();
  }

  function cancelDeliveryDriverForm() {
    state.deliveryDriverEditingId = "";
    state.deliveryDriverForm = null;
    renderWorkspace();
  }

  function updateDeliveryDriverForm(field, value) {
    state.deliveryDriverForm = {
      ...(state.deliveryDriverForm || {}),
      [field]: value,
    };
  }

  async function saveDeliveryDriver() {
    const payload = deliveryDriverPayload(state.deliveryDriverForm || {});
    const editingId = state.deliveryDriverEditingId;
    await runDeliveryAction(
      editingId ? `delivery-driver-edit:${editingId}` : "delivery-driver-add",
      async (context) => {
        if (editingId) {
          await api.updateDeliveryDriver(editingId, payload);
        } else {
          await api.createDeliveryDriver(payload);
        }
        if (isDeliveryMutationCurrent(context)) {
          state.deliveryDriverEditingId = "";
          state.deliveryDriverForm = null;
          await refreshDeliverySpecifications();
          await loadDeliveryRoute(context.route);
        }
      },
      (error) => {
        state.deliverySpecificationError = `Unable to save Driver. ${error.message}`;
      },
    );
  }

  async function deleteDeliveryDriver(driverId) {
    if (!confirmAction("Delete this Delivery driver?")) {
      return;
    }
    await runDeliveryAction(`delivery-driver-delete:${driverId}`, async (context) => {
      await api.deleteDeliveryDriver(driverId);
      if (isDeliveryMutationCurrent(context)) {
        await refreshDeliverySpecifications();
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliverySpecificationError = `Unable to delete Driver. ${error.message}`;
    });
  }

  async function toggleDeliveryDriverAvailability(driverId, isAvailable) {
    const driver = (state.deliverySpecifications?.drivers || []).find(
      (item) => item.driver_id === driverId,
    );
    if (!driver) {
      return;
    }
    await runDeliveryAction(`delivery-driver-toggle:${driverId}`, async (context) => {
      await api.updateDeliveryDriver(driverId, {
        ...defaultDeliveryDriverForm(driver),
        is_available: isAvailable,
      });
      if (isDeliveryMutationCurrent(context)) {
        await refreshDeliverySpecifications();
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliverySpecificationError =
        `Unable to update Driver availability. ${error.message}`;
    });
  }

  function startAddDeliveryVehicle() {
    state.deliverySpecificationTab = "vehicles";
    state.deliveryVehicleEditingId = "";
    state.deliveryVehicleForm = defaultDeliveryVehicleForm();
    state.deliverySpecificationError = "";
    renderWorkspace();
  }

  function startEditDeliveryVehicle(vehicleId) {
    const vehicle = (state.deliverySpecifications?.vehicles || state.deliveryBoard?.vehicles || [])
      .find((item) => item.vehicle_id === vehicleId);
    state.deliverySpecificationTab = "vehicles";
    state.deliveryVehicleEditingId = vehicleId;
    state.deliveryVehicleForm = defaultDeliveryVehicleForm(vehicle || {});
    state.deliverySpecificationError = "";
    renderWorkspace();
  }

  function cancelDeliveryVehicleForm() {
    state.deliveryVehicleEditingId = "";
    state.deliveryVehicleForm = null;
    renderWorkspace();
  }

  function updateDeliveryVehicleForm(field, value) {
    state.deliveryVehicleForm = {
      ...(state.deliveryVehicleForm || {}),
      [field]: value,
    };
  }

  async function saveDeliveryVehicle() {
    const payload = deliveryVehiclePayload(state.deliveryVehicleForm || {});
    const editingId = state.deliveryVehicleEditingId;
    await runDeliveryAction(
      editingId ? `delivery-vehicle-edit:${editingId}` : "delivery-vehicle-add",
      async (context) => {
        if (editingId) {
          await api.updateDeliveryVehicle(editingId, payload);
        } else {
          await api.createDeliveryVehicle(payload);
        }
        if (isDeliveryMutationCurrent(context)) {
          state.deliveryVehicleEditingId = "";
          state.deliveryVehicleForm = null;
          await refreshDeliverySpecifications();
          await loadDeliveryRoute(context.route);
        }
      },
      (error) => {
        state.deliverySpecificationError = `Unable to save Vehicle. ${error.message}`;
      },
    );
  }

  async function deleteDeliveryVehicle(vehicleId) {
    if (!confirmAction("Delete this Delivery vehicle?")) {
      return;
    }
    await runDeliveryAction(`delivery-vehicle-delete:${vehicleId}`, async (context) => {
      await api.deleteDeliveryVehicle(vehicleId);
      if (isDeliveryMutationCurrent(context)) {
        await refreshDeliverySpecifications();
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliverySpecificationError = `Unable to delete Vehicle. ${error.message}`;
    });
  }

  async function toggleDeliveryVehicleAvailability(vehicleId, isAvailable) {
    const vehicle = (state.deliverySpecifications?.vehicles || []).find(
      (item) => item.vehicle_id === vehicleId,
    );
    if (!vehicle) {
      return;
    }
    await runDeliveryAction(`delivery-vehicle-toggle:${vehicleId}`, async (context) => {
      await api.updateDeliveryVehicle(vehicleId, {
        ...defaultDeliveryVehicleForm(vehicle),
        is_available: isAvailable,
      });
      if (isDeliveryMutationCurrent(context)) {
        await refreshDeliverySpecifications();
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliverySpecificationError =
        `Unable to update Vehicle availability. ${error.message}`;
    });
  }

  function defaultDeliveryDriverForm(driver = {}) {
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

  function deliveryDriverPayload(form) {
    return {
      ...form,
      is_available: form.is_available !== false,
      pallet_only: Boolean(form.pallet_only),
    };
  }

  function defaultDeliveryVehicleForm(vehicle = {}) {
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

  function deliveryVehiclePayload(form) {
    return {
      ...form,
      is_available: form.is_available !== false,
      pallet_capacity: Number(form.pallet_capacity || 0),
      tub_capacity: Number(form.tub_capacity || 0),
      trolley_capacity: Number(form.trolley_capacity || 0),
      stillage_capacity: Number(form.stillage_capacity || 0),
    };
  }

  return {
    openDeliverySpecifications,
    closeDeliverySpecifications,
    setDeliverySpecificationTab,
    refreshDeliverySpecifications,
    startAddDeliveryDriver,
    startEditDeliveryDriver,
    cancelDeliveryDriverForm,
    updateDeliveryDriverForm,
    saveDeliveryDriver,
    deleteDeliveryDriver,
    toggleDeliveryDriverAvailability,
    startAddDeliveryVehicle,
    startEditDeliveryVehicle,
    cancelDeliveryVehicleForm,
    updateDeliveryVehicleForm,
    saveDeliveryVehicle,
    deleteDeliveryVehicle,
    toggleDeliveryVehicleAvailability,
    defaultDeliveryDriverForm,
    deliveryDriverPayload,
    defaultDeliveryVehicleForm,
    deliveryVehiclePayload,
  };
}
