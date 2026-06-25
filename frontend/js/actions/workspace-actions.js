import {
  apiApplyOpShopWorkspaceAssignments,
  apiAssignDeliveryWorkspaceOrder,
  apiAssignDeliveryWorkspaceVehicle,
  apiAssignOpShopWorkspaceCountrysideRouteGroup,
  apiCancelGeneratedDeliveryRunSheet,
  apiCancelGeneratedOpShopPickupCollection,
  apiClearDeliveryWorkspaceVehicle,
  apiCreateGeneratedDeliveryRunSheet,
  apiCreateGeneratedOpShopPickupCollection,
  apiExportDeliveryRunSheetExcel,
  apiExportOpShopPickupCollectionExcel,
  apiGetDeliveryWorkspaceBoard,
  apiGetOpShopWorkspaceBoard,
  apiGetWorkspaceMigrationStatus,
  apiListDeliveryRunSheets,
  apiListOpShopPickupCollections,
  apiSaveGeneratedDeliveryRunSheet,
  apiSaveGeneratedOpShopPickupCollection,
  apiUnassignDeliveryWorkspaceOrder,
  apiUnassignOpShopWorkspacePickup,
} from "../api/manual-dispatch-api.js";


const DELIVERY_ROUTES = new Set([
  "delivery/task-pool",
  "delivery/run-sheet",
  "delivery/history",
]);
const OPSHOP_ROUTES = new Set([
  "opshop/regular",
  "opshop/oncall",
  "opshop/countryside",
  "opshop/templates",
  "opshop/collections",
  "opshop/history",
]);
const DEFAULT_API = {
  applyOpShopWorkspaceAssignments: apiApplyOpShopWorkspaceAssignments,
  assignDeliveryWorkspaceOrder: apiAssignDeliveryWorkspaceOrder,
  assignDeliveryWorkspaceVehicle: apiAssignDeliveryWorkspaceVehicle,
  assignOpShopWorkspaceCountrysideRouteGroup: apiAssignOpShopWorkspaceCountrysideRouteGroup,
  cancelGeneratedDeliveryRunSheet: apiCancelGeneratedDeliveryRunSheet,
  cancelGeneratedOpShopPickupCollection: apiCancelGeneratedOpShopPickupCollection,
  clearDeliveryWorkspaceVehicle: apiClearDeliveryWorkspaceVehicle,
  createGeneratedDeliveryRunSheet: apiCreateGeneratedDeliveryRunSheet,
  createGeneratedOpShopPickupCollection: apiCreateGeneratedOpShopPickupCollection,
  exportDeliveryRunSheetExcel: apiExportDeliveryRunSheetExcel,
  exportOpShopPickupCollectionExcel: apiExportOpShopPickupCollectionExcel,
  getDeliveryWorkspaceBoard: apiGetDeliveryWorkspaceBoard,
  getOpShopWorkspaceBoard: apiGetOpShopWorkspaceBoard,
  getWorkspaceMigrationStatus: apiGetWorkspaceMigrationStatus,
  listDeliveryRunSheets: apiListDeliveryRunSheets,
  listOpShopPickupCollections: apiListOpShopPickupCollections,
  saveGeneratedDeliveryRunSheet: apiSaveGeneratedDeliveryRunSheet,
  saveGeneratedOpShopPickupCollection: apiSaveGeneratedOpShopPickupCollection,
  unassignDeliveryWorkspaceOrder: apiUnassignDeliveryWorkspaceOrder,
  unassignOpShopWorkspacePickup: apiUnassignOpShopWorkspacePickup,
};


export function createWorkspaceActions({ state, renderWorkspace, api = DEFAULT_API }) {
  let migrationStatusRequestVersion = 0;
  let deliveryWorkspaceRequestVersion = 0;
  let opshopWorkspaceRequestVersion = 0;

  async function loadWorkspaceRoute(route = state.workspaceRoute) {
    if (!state.isLoggedIn) {
      return;
    }
    if (route === "home") {
      await loadMigrationStatus();
      return;
    }
    if (DELIVERY_ROUTES.has(route)) {
      await loadDeliveryRoute(route);
      return;
    }
    if (OPSHOP_ROUTES.has(route)) {
      await loadOpShopRoute(route);
    }
  }

  async function loadMigrationStatus() {
    const route = state.workspaceRoute;
    const requestVersion = ++migrationStatusRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      route === "home" &&
      requestVersion === migrationStatusRequestVersion;

    state.isWorkspaceMigrationStatusLoading = true;
    state.workspaceMigrationStatusError = "";
    renderWorkspace();
    try {
      const status = await api.getWorkspaceMigrationStatus();
      if (!isCurrent()) {
        return;
      }
      state.workspaceMigrationStatus = status;
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      state.workspaceMigrationStatus = null;
      state.workspaceMigrationStatusError =
        `Unable to check workspace migration readiness. ${error.message}`;
    } finally {
      if (isCurrent()) {
        state.isWorkspaceMigrationStatusLoading = false;
        renderWorkspace();
      }
    }
  }

  async function loadMigrationStatusForHome(message = "") {
    state.workspaceRoute = "home";
    state.activeWorkspace = "";
    state.isDeliveryWorkspaceLoading = false;
    state.isOpShopWorkspaceLoading = false;
    state.deliveryBusyActionKey = "";
    state.opshopBusyActionKey = "";
    state.deliveryActionError = "";
    state.opshopActionError = "";
    if (typeof window !== "undefined") {
      if (window.location?.replace) {
        window.location.replace("#home");
      } else if (window.history?.replaceState) {
        window.history.replaceState(null, "", "#home");
        if (typeof window.dispatchEvent === "function" && typeof HashChangeEvent !== "undefined") {
          window.dispatchEvent(new HashChangeEvent("hashchange"));
        }
      }
    }
    state.isWorkspaceMigrationStatusLoading = true;
    state.workspaceMigrationStatusError = message;
    renderWorkspace();
    try {
      state.workspaceMigrationStatus = await api.getWorkspaceMigrationStatus();
    } catch (error) {
      state.workspaceMigrationStatus = null;
      state.workspaceMigrationStatusError =
        message || `Unable to check workspace migration readiness. ${error.message}`;
    } finally {
      state.isWorkspaceMigrationStatusLoading = false;
      renderWorkspace();
    }
  }

  async function handleWorkspaceMigrationGuard(error) {
    if (!error || error.status !== 409) {
      return false;
    }
    await loadMigrationStatusForHome(error.message);
    return true;
  }

  async function loadDeliveryRoute(route) {
    const dispatchDate = state.dispatchDate;
    const requestVersion = ++deliveryWorkspaceRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      requestVersion === deliveryWorkspaceRequestVersion;

    state.isDeliveryWorkspaceLoading = true;
    state.deliveryWorkspaceError = "";
    state.deliveryActionError = "";
    renderWorkspace();
    try {
      if (route === "delivery/task-pool") {
        const board = await api.getDeliveryWorkspaceBoard(dispatchDate);
        if (isCurrent()) {
          state.deliveryBoard = board;
          pruneDeliveryDrafts();
        }
      } else if (route === "delivery/run-sheet") {
        const [board, runSheets] = await Promise.all([
          api.getDeliveryWorkspaceBoard(dispatchDate),
          api.listDeliveryRunSheets(dispatchDate, ""),
        ]);
        if (isCurrent()) {
          state.deliveryBoard = board;
          state.deliveryRunSheets = runSheets || [];
          pruneDeliveryDrafts();
        }
      } else {
        const runSheets = await api.listDeliveryRunSheets(dispatchDate, "SAVED");
        if (isCurrent()) {
          state.deliveryRunSheets = runSheets || [];
        }
      }
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isCurrent()) {
        state.deliveryWorkspaceError =
          `Unable to load Order Delivery workspace. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isDeliveryWorkspaceLoading = false;
        renderWorkspace();
      }
    }
  }

  async function loadOpShopRoute(route) {
    const dispatchDate = state.dispatchDate;
    const requestVersion = ++opshopWorkspaceRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      requestVersion === opshopWorkspaceRequestVersion;

    state.isOpShopWorkspaceLoading = true;
    state.opshopWorkspaceError = "";
    state.opshopActionError = "";
    renderWorkspace();
    try {
      if (route === "opshop/collections") {
        const [board, collections] = await Promise.all([
          api.getOpShopWorkspaceBoard(dispatchDate),
          api.listOpShopPickupCollections(dispatchDate, ""),
        ]);
        if (isCurrent()) {
          state.opshopBoard = board;
          state.opshopPickupCollections = collections || [];
          pruneOpShopDrafts();
        }
      } else if (route === "opshop/history") {
        const collections = await api.listOpShopPickupCollections(
          dispatchDate,
          "SAVED",
        );
        if (isCurrent()) {
          state.opshopPickupCollections = collections || [];
        }
      } else {
        const board = await api.getOpShopWorkspaceBoard(dispatchDate);
        if (isCurrent()) {
          state.opshopBoard = board;
          pruneOpShopDrafts();
        }
      }
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isCurrent()) {
        state.opshopWorkspaceError =
          `Unable to load OP SHOP Pickup workspace. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isOpShopWorkspaceLoading = false;
        renderWorkspace();
      }
    }
  }

  async function updateDispatchDate(nextDate) {
    if (!nextDate || nextDate === state.dispatchDate) {
      return;
    }
    state.dispatchDate = nextDate;
    await loadWorkspaceRoute(state.workspaceRoute);
  }

  function updateDeliveryAssignmentDraft(orderId, field, value) {
    const current = state.deliveryAssignmentDrafts[orderId] || {};
    state.deliveryAssignmentDrafts = {
      ...state.deliveryAssignmentDrafts,
      [orderId]: {
        ...current,
        [field]: value,
      },
    };
    renderWorkspace();
  }

  async function applyDeliveryOrderAssignment(orderId) {
    const draft = getDeliveryAssignmentDraft(orderId);
    await runDeliveryAction(`delivery-assignment:${orderId}`, async () => {
      state.deliveryBoard = await api.assignDeliveryWorkspaceOrder({
        dispatch_date: state.dispatchDate,
        order_id: orderId,
        driver_id: draft.driver_id,
        trip_no: draft.trip_no || "trip1",
      });
      pruneDeliveryDrafts();
    });
  }

  async function unassignDeliveryOrder(orderId) {
    await runDeliveryAction(`delivery-unassign:${orderId}`, async () => {
      state.deliveryBoard = await api.unassignDeliveryWorkspaceOrder({
        dispatch_date: state.dispatchDate,
        order_id: orderId,
      });
      const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
      state.deliveryAssignmentDrafts = remaining;
      pruneDeliveryDrafts();
    });
  }

  function updateDeliveryVehicleDraft(deliveryDate, driverId, vehicleId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    state.deliveryVehicleDrafts = {
      ...state.deliveryVehicleDrafts,
      [key]: vehicleId,
    };
    renderWorkspace();
  }

  async function applyDeliveryVehicleAssignment(deliveryDate, driverId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    const currentAssignment = (state.deliveryBoard?.driver_vehicle_assignments || []).find(
      (assignment) =>
        assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
    );
    const vehicleId = Object.prototype.hasOwnProperty.call(state.deliveryVehicleDrafts, key)
      ? state.deliveryVehicleDrafts[key]
      : currentAssignment?.vehicle_id || "";
    await runDeliveryAction(`delivery-vehicle:${deliveryDate}:${driverId}`, async () => {
      state.deliveryBoard = await api.assignDeliveryWorkspaceVehicle({
        dispatch_date: state.dispatchDate,
        delivery_date: deliveryDate,
        driver_id: driverId,
        vehicle_id: vehicleId,
      });
      pruneDeliveryDrafts();
    });
  }

  async function clearDeliveryVehicleAssignment(deliveryDate, driverId) {
    await runDeliveryAction(`delivery-vehicle-clear:${deliveryDate}:${driverId}`, async () => {
      state.deliveryBoard = await api.clearDeliveryWorkspaceVehicle({
        dispatch_date: state.dispatchDate,
        delivery_date: deliveryDate,
        driver_id: driverId,
      });
      const key = deliveryVehicleKey(deliveryDate, driverId);
      const { [key]: _removed, ...remaining } = state.deliveryVehicleDrafts;
      state.deliveryVehicleDrafts = remaining;
      pruneDeliveryDrafts();
    });
  }

  async function generateDeliveryRunSheet(candidate) {
    await runDeliveryAction(
      `delivery-generate:${candidate.delivery_date}:${candidate.driver_id}`,
      async () => {
        await api.createGeneratedDeliveryRunSheet({
          dispatch_date: state.dispatchDate,
          delivery_date: candidate.delivery_date,
          driver_id: candidate.driver_id,
        });
        await loadDeliveryRoute("delivery/run-sheet");
      },
    );
  }

  async function saveDeliveryRunSheet(runSheetId) {
    await runDeliveryAction(`delivery-save:${runSheetId}`, async () => {
      await api.saveGeneratedDeliveryRunSheet(runSheetId, saveSnapshotPayload());
      await loadDeliveryRoute(state.workspaceRoute);
    });
  }

  async function cancelDeliveryRunSheet(runSheetId) {
    await runDeliveryAction(`delivery-cancel:${runSheetId}`, async () => {
      await api.cancelGeneratedDeliveryRunSheet(runSheetId);
      await loadDeliveryRoute("delivery/run-sheet");
    });
  }

  async function exportDeliveryRunSheet(runSheetId) {
    await runDeliveryAction(`delivery-export:${runSheetId}`, async () => {
      await api.exportDeliveryRunSheetExcel(runSheetId);
    });
  }

  function updateOpShopAssignmentDraft(pickupTaskId, driverId) {
    state.opshopAssignmentDrafts = {
      ...state.opshopAssignmentDrafts,
      [pickupTaskId]: driverId,
    };
    renderWorkspace();
  }

  async function applyOpShopAssignmentChanges(pickups) {
    const changedAssignments = changedOpShopAssignmentDrafts(pickups).map((pickup) => ({
        pickup_task_id: pickup.pickup_task_id,
        driver_id: state.opshopAssignmentDrafts[pickup.pickup_task_id] || null,
      }));

    if (!changedAssignments.length) {
      state.opshopActionError = "";
      renderWorkspace();
      return;
    }

    await runOpShopAction("opshop-apply-assignments", async () => {
      state.opshopBoard = await api.applyOpShopWorkspaceAssignments({
        dispatch_date: state.dispatchDate,
        assignments: changedAssignments,
      });
      state.opshopAssignmentDrafts = {};
      pruneOpShopDrafts();
    });
  }

  async function unassignOpShopPickup(pickupTaskId) {
    await runOpShopAction(`opshop-unassign:${pickupTaskId}`, async () => {
      state.opshopBoard = await api.unassignOpShopWorkspacePickup({
        dispatch_date: state.dispatchDate,
        pickup_task_id: pickupTaskId,
      });
      const { [pickupTaskId]: _removed, ...remaining } = state.opshopAssignmentDrafts;
      state.opshopAssignmentDrafts = remaining;
      pruneOpShopDrafts();
    });
  }

  function updateCountrysideRouteGroupDraft(routeGroupId, field, value) {
    const current = state.countrysideRouteGroupDrafts[routeGroupId] || {};
    state.countrysideRouteGroupDrafts = {
      ...state.countrysideRouteGroupDrafts,
      [routeGroupId]: {
        pickup_date: state.dispatchDate,
        assigned_driver_id: "",
        notes: "",
        ...current,
        [field]: value,
      },
    };
    renderWorkspace();
  }

  async function assignCountrysideRouteGroup(routeGroupId) {
    const draft = {
      pickup_date: state.dispatchDate,
      assigned_driver_id: "",
      notes: "",
      ...(state.countrysideRouteGroupDrafts[routeGroupId] || {}),
    };
    await runOpShopAction(`opshop-route-group:${routeGroupId}`, async () => {
      state.opshopBoard = await api.assignOpShopWorkspaceCountrysideRouteGroup(
        routeGroupId,
        {
          dispatch_date: state.dispatchDate,
          pickup_date: draft.pickup_date,
          assigned_driver_id: draft.assigned_driver_id,
          notes: draft.notes,
        },
      );
      const { [routeGroupId]: _removed, ...remaining } = state.countrysideRouteGroupDrafts;
      state.countrysideRouteGroupDrafts = remaining;
      pruneOpShopDrafts();
    });
  }

  async function generateOpShopPickupCollection(candidate) {
    await runOpShopAction(
      `opshop-generate:${candidate.pickup_date}:${candidate.driver_id}`,
      async () => {
        await api.createGeneratedOpShopPickupCollection({
          dispatch_date: state.dispatchDate,
          pickup_date: candidate.pickup_date,
          driver_id: candidate.driver_id,
        });
        await loadOpShopRoute("opshop/collections");
      },
    );
  }

  async function saveOpShopPickupCollection(collectionId) {
    await runOpShopAction(`opshop-save:${collectionId}`, async () => {
      await api.saveGeneratedOpShopPickupCollection(
        collectionId,
        saveSnapshotPayload(),
      );
      await loadOpShopRoute(state.workspaceRoute);
    });
  }

  async function cancelOpShopPickupCollection(collectionId) {
    await runOpShopAction(`opshop-cancel:${collectionId}`, async () => {
      await api.cancelGeneratedOpShopPickupCollection(collectionId);
      await loadOpShopRoute("opshop/collections");
    });
  }

  async function exportOpShopPickupCollection(collectionId) {
    await runOpShopAction(`opshop-export:${collectionId}`, async () => {
      await api.exportOpShopPickupCollectionExcel(collectionId);
    });
  }

  async function runDeliveryAction(actionKey, callback) {
    state.deliveryBusyActionKey = actionKey;
    state.deliveryActionError = "";
    renderWorkspace();
    try {
      await callback();
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      state.deliveryActionError = error.message;
    } finally {
      if (state.deliveryBusyActionKey === actionKey) {
        state.deliveryBusyActionKey = "";
        renderWorkspace();
      }
    }
  }

  async function runOpShopAction(actionKey, callback) {
    state.opshopBusyActionKey = actionKey;
    state.opshopActionError = "";
    renderWorkspace();
    try {
      await callback();
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      state.opshopActionError = error.message;
    } finally {
      if (state.opshopBusyActionKey === actionKey) {
        state.opshopBusyActionKey = "";
        renderWorkspace();
      }
    }
  }

  function getDeliveryAssignmentDraft(orderId) {
    const assignment = findDeliveryAssignment(orderId);
    const current = state.deliveryAssignmentDrafts[orderId] || {};
    return {
      driver_id: current.driver_id ?? assignment?.driver_id ?? "",
      trip_no: current.trip_no ?? assignment?.trip_no ?? "trip1",
    };
  }

  function findDeliveryAssignment(orderId) {
    return (state.deliveryBoard?.assignments || []).find(
      (assignment) => assignment.task_id === orderId,
    );
  }

  function pruneDeliveryDrafts() {
    const orderIds = new Set((state.deliveryBoard?.orders || []).map((order) => order.order_id));
    state.deliveryAssignmentDrafts = Object.fromEntries(
      Object.entries(state.deliveryAssignmentDrafts || {}).filter(([orderId]) =>
        orderIds.has(orderId),
      ),
    );

    const vehicleKeys = new Set();
    (state.deliveryBoard?.driver_vehicle_assignments || []).forEach((assignment) => {
      vehicleKeys.add(deliveryVehicleKey(assignment.delivery_date, assignment.driver_id));
    });
    (state.deliveryBoard?.assignments || []).forEach((assignment) => {
      const order = (state.deliveryBoard?.orders || []).find(
        (item) => item.order_id === assignment.task_id,
      );
      if (order?.delivery_date) {
        vehicleKeys.add(deliveryVehicleKey(order.delivery_date, assignment.driver_id));
      }
    });
    state.deliveryVehicleDrafts = Object.fromEntries(
      Object.entries(state.deliveryVehicleDrafts || {}).filter(([key]) =>
        vehicleKeys.has(key),
      ),
    );
  }

  function pruneOpShopDrafts() {
    const pickupIds = new Set(
      (state.opshopBoard?.opshop_pickups || []).map((pickup) => pickup.pickup_task_id),
    );
    state.opshopAssignmentDrafts = Object.fromEntries(
      Object.entries(state.opshopAssignmentDrafts || {}).filter(([pickupTaskId]) =>
        pickupIds.has(pickupTaskId),
      ),
    );
    const routeGroupIds = new Set(
      (state.opshopBoard?.countryside_route_groups || []).map(
        (routeGroup) => routeGroup.route_group_id,
      ),
    );
    state.countrysideRouteGroupDrafts = Object.fromEntries(
      Object.entries(state.countrysideRouteGroupDrafts || {}).filter(([routeGroupId]) =>
        routeGroupIds.has(routeGroupId),
      ),
    );
  }

  function saveSnapshotPayload() {
    return {
      saved_by_account_name: state.accountName || null,
      saved_by_account_id: state.accountId || null,
    };
  }

  function changedOpShopAssignmentDrafts(pickups) {
    return (pickups || []).filter((pickup) => {
      if (!Object.prototype.hasOwnProperty.call(
        state.opshopAssignmentDrafts,
        pickup.pickup_task_id,
      )) {
        return false;
      }
      return state.opshopAssignmentDrafts[pickup.pickup_task_id] !== currentOpShopDriverId(pickup);
    });
  }

  return {
    applyDeliveryOrderAssignment,
    applyDeliveryVehicleAssignment,
    applyOpShopAssignmentChanges,
    assignCountrysideRouteGroup,
    cancelDeliveryRunSheet,
    cancelOpShopPickupCollection,
    clearDeliveryVehicleAssignment,
    exportDeliveryRunSheet,
    exportOpShopPickupCollection,
    generateDeliveryRunSheet,
    generateOpShopPickupCollection,
    loadWorkspaceRoute,
    saveDeliveryRunSheet,
    saveOpShopPickupCollection,
    unassignDeliveryOrder,
    unassignOpShopPickup,
    updateCountrysideRouteGroupDraft,
    updateDeliveryAssignmentDraft,
    updateDeliveryVehicleDraft,
    updateDispatchDate,
    updateOpShopAssignmentDraft,
  };
}


function currentOpShopDriverId(pickup) {
  return pickup?.assigned_driver_id || pickup?.driver_id || "";
}


function deliveryVehicleKey(deliveryDate, driverId) {
  return `${deliveryDate || ""}|${driverId || ""}`;
}
