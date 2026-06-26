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
  "delivery/trip-summary",
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


export function createWorkspaceActions({
  state,
  renderWorkspace,
  api = DEFAULT_API,
  confirmAction = defaultConfirmAction,
}) {
  let migrationStatusRequestVersion = 0;
  let deliveryWorkspaceRequestVersion = 0;
  let opshopWorkspaceRequestVersion = 0;
  let actionTokenCounter = 0;

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
    state.deliveryBusyActionKeys = {};
    state.opshopBusyActionKeys = {};
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
      } else if (route === "delivery/trip-summary" || route === "delivery/run-sheet") {
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
    clearWorkspaceDraftsForDispatchDateChange();
    state.dispatchDate = nextDate;
    state.deliveryTripSummaryDate = nextDate;
    await loadWorkspaceRoute(state.workspaceRoute);
  }

  function updateDeliveryTripSummaryDate(nextDate) {
    state.deliveryTripSummaryDate = nextDate || state.dispatchDate;
    state.deliveryTripAddOrderDrafts = {};
    renderWorkspace();
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
    await runDeliveryAction(`delivery-assignment:${orderId}`, async (context) => {
      await api.assignDeliveryWorkspaceOrder({
        dispatch_date: context.dispatchDate,
        order_id: orderId,
        driver_id: draft.driver_id,
        trip_no: draft.trip_no || "trip1",
      });
      if (isDeliveryMutationCurrent(context)) {
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        await loadDeliveryRoute(context.route);
      }
    });
  }

  function updateDeliveryTripAddOrderDraft(deliveryDate, driverId, tripNo, orderId) {
    const key = deliveryTripAddOrderKey(deliveryDate, driverId, tripNo);
    state.deliveryTripAddOrderDrafts = {
      ...state.deliveryTripAddOrderDrafts,
      [key]: orderId,
    };
    renderWorkspace();
  }

  async function addDeliveryOrderToTrip(deliveryDate, driverId, tripNo) {
    const key = deliveryTripAddOrderKey(deliveryDate, driverId, tripNo);
    const orderId = state.deliveryTripAddOrderDrafts[key] || "";
    if (!orderId) {
      state.deliveryActionError = "Select an unassigned Delivery Order before adding it to a trip.";
      renderWorkspace();
      return;
    }
    await runDeliveryAction(`delivery-add-order:${deliveryDate}:${driverId}:${tripNo}`, async (context) => {
      await api.assignDeliveryWorkspaceOrder({
        dispatch_date: context.dispatchDate,
        order_id: orderId,
        driver_id: driverId,
        trip_no: tripNo,
      });
      if (isDeliveryMutationCurrent(context)) {
        const { [key]: _removed, ...remaining } = state.deliveryTripAddOrderDrafts;
        state.deliveryTripAddOrderDrafts = remaining;
        await loadDeliveryRoute(context.route);
      }
    });
  }

  async function moveDeliveryOrderToTrip(orderId, driverId, tripNo) {
    await runDeliveryAction(`delivery-move:${orderId}:${tripNo}`, async (context) => {
      await api.assignDeliveryWorkspaceOrder({
        dispatch_date: context.dispatchDate,
        order_id: orderId,
        driver_id: driverId,
        trip_no: tripNo,
      });
      if (isDeliveryMutationCurrent(context)) {
        await loadDeliveryRoute(context.route);
      }
    });
  }

  async function unassignDeliveryOrder(orderId) {
    await runDeliveryAction(`delivery-unassign:${orderId}`, async (context) => {
      await api.unassignDeliveryWorkspaceOrder({
        dispatch_date: context.dispatchDate,
        order_id: orderId,
      });
      if (isDeliveryMutationCurrent(context)) {
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        await loadDeliveryRoute(context.route);
      }
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
    await runDeliveryAction(`delivery-vehicle:${deliveryDate}:${driverId}`, async (context) => {
      await api.assignDeliveryWorkspaceVehicle({
        dispatch_date: context.dispatchDate,
        delivery_date: deliveryDate,
        driver_id: driverId,
        vehicle_id: vehicleId,
      });
      if (isDeliveryMutationCurrent(context)) {
        const { [key]: _removed, ...remaining } = state.deliveryVehicleDrafts;
        state.deliveryVehicleDrafts = remaining;
        await loadDeliveryRoute(context.route);
      }
    });
  }

  async function clearDeliveryVehicleAssignment(deliveryDate, driverId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    await runDeliveryAction(`delivery-vehicle-clear:${deliveryDate}:${driverId}`, async (context) => {
      await api.clearDeliveryWorkspaceVehicle({
        dispatch_date: context.dispatchDate,
        delivery_date: deliveryDate,
        driver_id: driverId,
      });
      if (isDeliveryMutationCurrent(context)) {
        const { [key]: _removed, ...remaining } = state.deliveryVehicleDrafts;
        state.deliveryVehicleDrafts = remaining;
        await loadDeliveryRoute(context.route);
      }
    });
  }

  async function generateDeliveryRunSheet(candidate) {
    await runDeliveryAction(
      `delivery-generate:${candidate.delivery_date}:${candidate.driver_id}`,
      async (context) => {
        await api.createGeneratedDeliveryRunSheet({
          dispatch_date: context.dispatchDate,
          delivery_date: candidate.delivery_date,
          driver_id: candidate.driver_id,
        });
        await navigateToDeliveryRunSheets(context);
      },
    );
  }

  async function saveDeliveryRunSheet(runSheetId) {
    await runDeliveryAction(`delivery-save:${runSheetId}`, async (context) => {
      await api.saveGeneratedDeliveryRunSheet(runSheetId, saveSnapshotPayload());
      if (isDeliveryMutationCurrent(context)) {
        await loadDeliveryRoute(context.route);
      }
    });
  }

  async function cancelDeliveryRunSheet(runSheetId) {
    const confirmed = confirmAction(
      "Cancel this generated Delivery Run Sheet? Captured orders will return to the Delivery Task Pool.",
    );
    if (!confirmed) {
      return;
    }
    await runDeliveryAction(`delivery-cancel:${runSheetId}`, async (context) => {
      await api.cancelGeneratedDeliveryRunSheet(runSheetId);
      if (isDeliveryMutationCurrent(context)) {
        await loadDeliveryRoute(context.route);
      }
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
    const changedPickups = changedOpShopAssignmentDrafts(pickups);
    const changedAssignments = changedPickups.map((pickup) => ({
      pickup_task_id: pickup.pickup_task_id,
      driver_id: state.opshopAssignmentDrafts[pickup.pickup_task_id] || null,
    }));
    const submittedPickupIds = new Set(
      changedAssignments.map((assignment) => assignment.pickup_task_id),
    );

    if (!changedAssignments.length) {
      state.opshopActionError = "";
      renderWorkspace();
      return;
    }

    await runOpShopAction("opshop-apply-assignments", async (context) => {
      await api.applyOpShopWorkspaceAssignments({
        dispatch_date: context.dispatchDate,
        assignments: changedAssignments,
      });
      if (isOpShopMutationCurrent(context)) {
        state.opshopAssignmentDrafts = Object.fromEntries(
          Object.entries(state.opshopAssignmentDrafts || {}).filter(
            ([pickupTaskId]) => !submittedPickupIds.has(pickupTaskId),
          ),
        );
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function unassignOpShopPickup(pickupTaskId) {
    await runOpShopAction(`opshop-unassign:${pickupTaskId}`, async (context) => {
      await api.unassignOpShopWorkspacePickup({
        dispatch_date: context.dispatchDate,
        pickup_task_id: pickupTaskId,
      });
      if (isOpShopMutationCurrent(context)) {
        const { [pickupTaskId]: _removed, ...remaining } = state.opshopAssignmentDrafts;
        state.opshopAssignmentDrafts = remaining;
        await loadOpShopRoute(context.route);
      }
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
    await runOpShopAction(`opshop-route-group:${routeGroupId}`, async (context) => {
      await api.assignOpShopWorkspaceCountrysideRouteGroup(
        routeGroupId,
        {
          dispatch_date: context.dispatchDate,
          pickup_date: draft.pickup_date,
          assigned_driver_id: draft.assigned_driver_id,
          notes: draft.notes,
        },
      );
      if (isOpShopMutationCurrent(context)) {
        const { [routeGroupId]: _removed, ...remaining } = state.countrysideRouteGroupDrafts;
        state.countrysideRouteGroupDrafts = remaining;
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function generateOpShopPickupCollection(candidate) {
    await runOpShopAction(
      `opshop-generate:${candidate.pickup_date}:${candidate.driver_id}`,
      async (context) => {
        await api.createGeneratedOpShopPickupCollection({
          dispatch_date: context.dispatchDate,
          pickup_date: candidate.pickup_date,
          driver_id: candidate.driver_id,
        });
        if (isOpShopMutationCurrent(context)) {
          await loadOpShopRoute(context.route);
        }
      },
    );
  }

  async function saveOpShopPickupCollection(collectionId) {
    await runOpShopAction(`opshop-save:${collectionId}`, async (context) => {
      await api.saveGeneratedOpShopPickupCollection(
        collectionId,
        saveSnapshotPayload(),
      );
      if (isOpShopMutationCurrent(context)) {
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function cancelOpShopPickupCollection(collectionId) {
    const confirmed = confirmAction(
      "Cancel this generated OP SHOP Pickup Collection? Captured pickups will return to the OP SHOP workspace.",
    );
    if (!confirmed) {
      return;
    }
    await runOpShopAction(`opshop-cancel:${collectionId}`, async (context) => {
      await api.cancelGeneratedOpShopPickupCollection(collectionId);
      if (isOpShopMutationCurrent(context)) {
        await loadOpShopRoute(context.route);
      }
    });
  }

  async function exportOpShopPickupCollection(collectionId) {
    await runOpShopAction(`opshop-export:${collectionId}`, async () => {
      await api.exportOpShopPickupCollectionExcel(collectionId);
    });
  }

  async function runDeliveryAction(actionKey, callback) {
    const context = captureMutationContext();
    const token = nextActionToken();
    state.deliveryBusyActionKeys = state.deliveryBusyActionKeys || {};
    setBusyAction(state.deliveryBusyActionKeys, actionKey, token);
    state.deliveryActionError = "";
    renderWorkspace();
    try {
      await callback(context);
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isDeliveryMutationCurrent(context)) {
        state.deliveryActionError = error.message;
      }
    } finally {
      if (clearBusyAction(state.deliveryBusyActionKeys, actionKey, token)) {
        renderWorkspace();
      }
    }
  }

  async function runOpShopAction(actionKey, callback) {
    const context = captureMutationContext();
    const token = nextActionToken();
    state.opshopBusyActionKeys = state.opshopBusyActionKeys || {};
    setBusyAction(state.opshopBusyActionKeys, actionKey, token);
    state.opshopActionError = "";
    renderWorkspace();
    try {
      await callback(context);
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isOpShopMutationCurrent(context)) {
        state.opshopActionError = error.message;
      }
    } finally {
      if (clearBusyAction(state.opshopBusyActionKeys, actionKey, token)) {
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
    state.deliveryTripAddOrderDrafts = Object.fromEntries(
      Object.entries(state.deliveryTripAddOrderDrafts || {}).filter(([, orderId]) =>
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

  function clearWorkspaceDraftsForDispatchDateChange() {
    state.deliveryAssignmentDrafts = {};
    state.deliveryTripAddOrderDrafts = {};
    state.deliveryVehicleDrafts = {};
    state.opshopAssignmentDrafts = {};
    state.countrysideRouteGroupDrafts = {};
    state.deliveryActionError = "";
    state.opshopActionError = "";
    state.deliveryBusyActionKeys = {};
    state.opshopBusyActionKeys = {};
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

  function captureMutationContext() {
    return {
      route: state.workspaceRoute,
      dispatchDate: state.dispatchDate,
      activeWorkspace: state.activeWorkspace,
    };
  }

  function nextActionToken() {
    actionTokenCounter += 1;
    return `action-${actionTokenCounter}`;
  }

  async function navigateToDeliveryRunSheets(context) {
    if (!context || context.activeWorkspace !== "delivery") {
      return;
    }
    state.workspaceRoute = "delivery/run-sheet";
    state.activeWorkspace = "delivery";
    if (typeof window !== "undefined" && window.history?.pushState) {
      window.history.pushState(null, "", "#delivery/run-sheet");
    }
    await loadDeliveryRoute("delivery/run-sheet");
  }

  function isDeliveryMutationCurrent(context) {
    return (
      state.isLoggedIn &&
      context &&
      state.workspaceRoute === context.route &&
      state.dispatchDate === context.dispatchDate &&
      state.activeWorkspace === context.activeWorkspace &&
      DELIVERY_ROUTES.has(context.route)
    );
  }

  function isOpShopMutationCurrent(context) {
    return (
      state.isLoggedIn &&
      context &&
      state.workspaceRoute === context.route &&
      state.dispatchDate === context.dispatchDate &&
      state.activeWorkspace === context.activeWorkspace &&
      OPSHOP_ROUTES.has(context.route)
    );
  }

  return {
    applyDeliveryOrderAssignment,
    applyDeliveryVehicleAssignment,
    addDeliveryOrderToTrip,
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
    moveDeliveryOrderToTrip,
    saveDeliveryRunSheet,
    saveOpShopPickupCollection,
    unassignDeliveryOrder,
    unassignOpShopPickup,
    updateCountrysideRouteGroupDraft,
    updateDeliveryAssignmentDraft,
    updateDeliveryTripAddOrderDraft,
    updateDeliveryTripSummaryDate,
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


function deliveryTripAddOrderKey(deliveryDate, driverId, tripNo) {
  return `${deliveryDate || ""}|${driverId || ""}|${tripNo || ""}`;
}


function setBusyAction(registry, actionKey, token) {
  registry[actionKey] = token;
}


function clearBusyAction(registry, actionKey, token) {
  if (!registry || registry[actionKey] !== token) {
    return false;
  }
  delete registry[actionKey];
  return true;
}


function defaultConfirmAction(message) {
  if (typeof window === "undefined" || typeof window.confirm !== "function") {
    return true;
  }
  return window.confirm(message);
}
