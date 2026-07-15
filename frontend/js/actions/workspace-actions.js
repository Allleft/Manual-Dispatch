import {
  apiApplyOpShopWorkspaceAssignments,
  apiAssignDeliveryWorkspaceOrder,
  apiAssignDeliveryWorkspaceVehicle,
  apiAssignOpShopWorkspaceCountrysideRouteGroup,
  apiCancelGeneratedDeliveryRunSheet,
  apiCancelGeneratedOpShopPickupCollection,
  apiClearDeliveryWorkspaceVehicle,
  apiCommitDeliveryAttacheInvoices,
  apiCancelDeliveryOrder,
  apiCreateDeliveryDriver,
  apiCreateDeliveryOrder,
  apiCreateDeliveryVehicle,
  apiCreateGeneratedDeliveryRunSheet,
  apiCreateGeneratedOpShopPickupCollection,
  apiDeleteDeliveryDriver,
  apiDeleteDeliveryVehicle,
  apiExportDeliveryRunSheetExcel,
  apiExportDeliveryRunSheetsExcel,
  apiExportOpShopPickupCollectionExcel,
  apiExportOpShopPickupCollectionsExcel,
  apiGetDeliverySpecifications,
  apiGetDeliveryTripSummary,
  apiGetDeliveryWorkspaceBoard,
  apiGetOpShopTripSummary,
  apiGetOpShopWorkspaceBoard,
  apiGetWorkspaceMigrationStatus,
  apiListDeliveryRunSheets,
  apiListDeliveryRunSheetsByDispatchAndDeliveryDate,
  apiListDeliveryRunSheetsByDeliveryDate,
  apiListOpShopPickupCollections,
  apiListOpShopPickupCollectionsByDispatchAndPickupDate,
  apiListOpShopPickupCollectionsByPickupDate,
  apiPreviewDeliveryAttacheInvoices,
  apiSaveGeneratedDeliveryRunSheet,
  apiSaveGeneratedOpShopPickupCollection,
  apiUnassignDeliveryWorkspaceOrder,
  apiUnassignOpShopWorkspacePickup,
  apiUpdateDeliveryDriver,
  apiUpdateDeliveryOrder,
  apiUpdateDeliveryVehicle,
} from "../api/manual-dispatch-api.js";
import {
  getDeliveryVehicleConflictDriverNames,
} from "../utils/delivery-vehicle-utils.js";
import { toggleCollapsedPickupDateGroup } from "../utils/opshop-date-group-utils.js";
import { captureWindowScroll, restoreWindowScroll } from "../utils/scroll-utils.js";


const DELIVERY_ROUTES = new Set([
  "delivery/task-pool",
  "delivery/trip-summary",
  "delivery/run-sheet",
  "delivery/history",
]);
const OPSHOP_ROUTES = new Set([
  "opshop/task-pool/regular",
  "opshop/task-pool/oncall",
  "opshop/task-pool/countryside",
  "opshop/trip-summary",
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
  cancelDeliveryOrder: apiCancelDeliveryOrder,
  cancelGeneratedDeliveryRunSheet: apiCancelGeneratedDeliveryRunSheet,
  cancelGeneratedOpShopPickupCollection: apiCancelGeneratedOpShopPickupCollection,
  clearDeliveryWorkspaceVehicle: apiClearDeliveryWorkspaceVehicle,
  commitDeliveryAttacheInvoices: apiCommitDeliveryAttacheInvoices,
  createDeliveryDriver: apiCreateDeliveryDriver,
  createDeliveryOrder: apiCreateDeliveryOrder,
  createDeliveryVehicle: apiCreateDeliveryVehicle,
  createGeneratedDeliveryRunSheet: apiCreateGeneratedDeliveryRunSheet,
  createGeneratedOpShopPickupCollection: apiCreateGeneratedOpShopPickupCollection,
  deleteDeliveryDriver: apiDeleteDeliveryDriver,
  deleteDeliveryVehicle: apiDeleteDeliveryVehicle,
  exportDeliveryRunSheetExcel: apiExportDeliveryRunSheetExcel,
  exportDeliveryRunSheetsExcel: apiExportDeliveryRunSheetsExcel,
  exportOpShopPickupCollectionExcel: apiExportOpShopPickupCollectionExcel,
  exportOpShopPickupCollectionsExcel: apiExportOpShopPickupCollectionsExcel,
  getDeliverySpecifications: apiGetDeliverySpecifications,
  getDeliveryTripSummary: apiGetDeliveryTripSummary,
  getDeliveryWorkspaceBoard: apiGetDeliveryWorkspaceBoard,
  getOpShopTripSummary: apiGetOpShopTripSummary,
  getOpShopWorkspaceBoard: apiGetOpShopWorkspaceBoard,
  getWorkspaceMigrationStatus: apiGetWorkspaceMigrationStatus,
  listDeliveryRunSheets: apiListDeliveryRunSheets,
  listDeliveryRunSheetsByDispatchAndDeliveryDate: apiListDeliveryRunSheetsByDispatchAndDeliveryDate,
  listDeliveryRunSheetsByDeliveryDate: apiListDeliveryRunSheetsByDeliveryDate,
  listOpShopPickupCollections: apiListOpShopPickupCollections,
  listOpShopPickupCollectionsByDispatchAndPickupDate: apiListOpShopPickupCollectionsByDispatchAndPickupDate,
  listOpShopPickupCollectionsByPickupDate: apiListOpShopPickupCollectionsByPickupDate,
  previewDeliveryAttacheInvoices: apiPreviewDeliveryAttacheInvoices,
  saveGeneratedDeliveryRunSheet: apiSaveGeneratedDeliveryRunSheet,
  saveGeneratedOpShopPickupCollection: apiSaveGeneratedOpShopPickupCollection,
  unassignDeliveryWorkspaceOrder: apiUnassignDeliveryWorkspaceOrder,
  unassignOpShopWorkspacePickup: apiUnassignOpShopWorkspacePickup,
  updateDeliveryDriver: apiUpdateDeliveryDriver,
  updateDeliveryOrder: apiUpdateDeliveryOrder,
  updateDeliveryVehicle: apiUpdateDeliveryVehicle,
};


export function createWorkspaceActions({
  state,
  renderWorkspace,
  api = DEFAULT_API,
  confirmAction = defaultConfirmAction,
  navigateWorkspaceRoute = null,
}) {
  let migrationStatusRequestVersion = 0;
  let deliveryWorkspaceRequestVersion = 0;
  let opshopWorkspaceRequestVersion = 0;
  let deliveryAttachePreviewRequestVersion = 0;
  let deliverySpecificationRequestVersion = 0;
  let deliveryVehicleMutationVersion = 0;
  let deliveryVehicleQueueIdCounter = 0;
  let actionTokenCounter = 0;
  const deliveryVehicleQueues = new Map();
  const deliveryVehiclePhysicalTails = new Map();

  async function loadWorkspaceRoute(route = state.workspaceRoute) {
    clearGenerationConfirmationsForRoute(route);
    if (route !== "delivery/trip-summary") {
      clearDeliveryVehicleTransientState();
    }
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
    invalidateDeliveryAttachePreview();
    state.workspaceRoute = "home";
    state.activeWorkspace = "";
    state.isDeliveryWorkspaceLoading = false;
    state.isOpShopWorkspaceLoading = false;
    state.deliveryBusyActionKeys = {};
    state.opshopBusyActionKeys = {};
    state.deliveryGenerationConfirmation = null;
    state.opshopGenerationConfirmation = null;
    state.deliveryActionError = "";
    state.opshopActionError = "";
    state.deliveryOrderDetailId = "";
    state.deliveryOrderDetailReadOnly = false;
    state.deliveryOrderForm = {};
    state.deliveryOrderFormMode = "";
    state.deliveryOrderModalError = "";
    state.deliveryAttacheImportState = defaultDeliveryAttacheImportState();
    state.deliverySpecificationModalOpen = false;
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    state.deliverySpecificationError = "";
    state.deliverySpecificationBusyKey = "";
    clearDeliveryVehicleTransientState();
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
    if (route === "delivery/history") {
      await loadDeliverySavedHistoryData(route);
      return;
    }
    const dispatchDate = state.dispatchDate;
    const requestVersion = ++deliveryWorkspaceRequestVersion;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      requestVersion === deliveryWorkspaceRequestVersion;

    if (route !== "delivery/task-pool") {
      clearDeliveryTaskPoolModals();
    }
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
      } else if (route === "delivery/trip-summary") {
        const deliveryDate = state.deliveryTripSummaryDate || dispatchDate;
        await loadDeliveryTripSummaryData(route, deliveryDate, requestVersion);
        return;
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

  async function loadDeliverySavedHistoryData(
    route = state.workspaceRoute,
    historyDate = state.deliverySavedHistoryDate,
    requestVersion = ++deliveryWorkspaceRequestVersion,
  ) {
    const requestedHistoryDate =
      historyDate || state.deliverySavedHistoryDate || state.dispatchDate;
    state.deliverySavedHistoryDate = requestedHistoryDate;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === "delivery/history" &&
      route === "delivery/history" &&
      state.deliverySavedHistoryDate === requestedHistoryDate &&
      requestVersion === deliveryWorkspaceRequestVersion;

    state.deliverySavedHistoryRunSheets = [];
    state.isDeliveryWorkspaceLoading = true;
    state.deliveryWorkspaceError = "";
    state.deliveryActionError = "";
    renderWorkspace();
    try {
      const runSheets = await api.listDeliveryRunSheetsByDeliveryDate(
        requestedHistoryDate,
        "SAVED",
      );
      if (isCurrent()) {
        state.deliverySavedHistoryRunSheets = sortDeliverySavedHistory(runSheets);
      }
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isCurrent()) {
        state.deliveryWorkspaceError =
          `Unable to load Saved Run Sheet history. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isDeliveryWorkspaceLoading = false;
        renderWorkspace();
      }
    }
  }

  async function loadDeliveryTripSummaryData(
    route = state.workspaceRoute,
    deliveryDate = state.deliveryTripSummaryDate || state.dispatchDate,
    requestVersion = ++deliveryWorkspaceRequestVersion,
  ) {
    const dispatchDate = state.dispatchDate;
    const scopedDeliveryDate = deliveryDate || dispatchDate;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      state.deliveryTripSummaryDate === scopedDeliveryDate &&
      requestVersion === deliveryWorkspaceRequestVersion;

    const [board, runSheets] = await Promise.all([
      api.getDeliveryTripSummary({
        dispatchDate,
        deliveryDate: scopedDeliveryDate,
      }),
      api.listDeliveryRunSheetsByDispatchAndDeliveryDate(
        dispatchDate,
        scopedDeliveryDate,
        "",
      ),
    ]);
    if (isCurrent()) {
      state.deliveryTripSummaryBoard = board;
      state.deliveryTripSummaryRunSheets = runSheets || [];
      pruneDeliveryVehicleDrafts(state.deliveryTripSummaryBoard);
    }
  }

  async function loadOpShopRoute(route) {
    if (route === "opshop/history") {
      await loadOpShopSavedHistoryData(route);
      return;
    }
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
      if (route === "opshop/trip-summary") {
        const pickupDate = state.opshopTripSummaryDate || dispatchDate;
        await loadOpShopTripSummaryData(route, pickupDate, requestVersion);
        return;
      } else if (route === "opshop/collections") {
        const [board, collections] = await Promise.all([
          api.getOpShopWorkspaceBoard(dispatchDate),
          api.listOpShopPickupCollections(dispatchDate, ""),
        ]);
        if (isCurrent()) {
          state.opshopBoard = board;
          state.opshopPickupCollections = collections || [];
          pruneOpShopDrafts();
        }
      } else if (route.startsWith("opshop/task-pool/")) {
        const [board, collections] = await Promise.all([
          api.getOpShopWorkspaceBoard(dispatchDate),
          api.listOpShopPickupCollections(dispatchDate, ""),
        ]);
        if (isCurrent()) {
          state.opshopBoard = board;
          state.opshopPickupCollections = collections || [];
          pruneOpShopDrafts();
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

  async function loadOpShopSavedHistoryData(
    route = state.workspaceRoute,
    historyDate = state.opshopSavedHistoryDate,
    requestVersion = ++opshopWorkspaceRequestVersion,
  ) {
    const requestedHistoryDate =
      historyDate || state.opshopSavedHistoryDate || state.dispatchDate;
    state.opshopSavedHistoryDate = requestedHistoryDate;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === "opshop/history" &&
      route === "opshop/history" &&
      state.opshopSavedHistoryDate === requestedHistoryDate &&
      requestVersion === opshopWorkspaceRequestVersion;

    state.opshopSavedHistoryCollections = [];
    state.isOpShopWorkspaceLoading = true;
    state.opshopWorkspaceError = "";
    state.opshopActionError = "";
    renderWorkspace();
    try {
      const collections = await api.listOpShopPickupCollectionsByPickupDate(
        requestedHistoryDate,
        "SAVED",
      );
      if (isCurrent()) {
        state.opshopSavedHistoryCollections =
          sortOpShopSavedHistory(collections);
      }
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isCurrent()) {
        state.opshopWorkspaceError =
          `Unable to load Saved Pickup Collection history. ${error.message}`;
      }
    } finally {
      if (isCurrent()) {
        state.isOpShopWorkspaceLoading = false;
        renderWorkspace();
      }
    }
  }

  async function loadOpShopTripSummaryData(
    route = state.workspaceRoute,
    pickupDate = state.opshopTripSummaryDate || state.dispatchDate,
    requestVersion = ++opshopWorkspaceRequestVersion,
  ) {
    const dispatchDate = state.dispatchDate;
    const scopedPickupDate = pickupDate || dispatchDate;
    const isCurrent = () =>
      state.isLoggedIn &&
      state.workspaceRoute === route &&
      state.dispatchDate === dispatchDate &&
      state.opshopTripSummaryDate === scopedPickupDate &&
      requestVersion === opshopWorkspaceRequestVersion;

    const [board, collections] = await Promise.all([
      api.getOpShopTripSummary({
        dispatchDate,
        pickupDate: scopedPickupDate,
      }),
      api.listOpShopPickupCollectionsByDispatchAndPickupDate(
        dispatchDate,
        scopedPickupDate,
        "",
      ),
    ]);
    if (isCurrent()) {
      state.opshopTripSummaryBoard = board;
      state.opshopTripSummaryCollections = collections || [];
    }
  }

  async function updateDispatchDate(nextDate) {
    if (!nextDate || nextDate === state.dispatchDate) {
      return;
    }
    clearWorkspaceDraftsForDispatchDateChange();
    state.dispatchDate = nextDate;
    state.deliveryTripSummaryDate = nextDate;
    state.opshopTripSummaryDate = nextDate;
    await loadWorkspaceRoute(state.workspaceRoute);
  }

  async function updateDeliverySavedHistoryDate(nextDate) {
    state.deliverySavedHistoryDate =
      nextDate || state.deliverySavedHistoryDate || state.dispatchDate;
    if (state.workspaceRoute === "delivery/history") {
      await loadDeliverySavedHistoryData(
        state.workspaceRoute,
        state.deliverySavedHistoryDate,
      );
      return;
    }
    renderWorkspace();
  }

  async function updateOpShopSavedHistoryDate(nextDate) {
    state.opshopSavedHistoryDate =
      nextDate || state.opshopSavedHistoryDate || state.dispatchDate;
    if (state.workspaceRoute === "opshop/history") {
      await loadOpShopSavedHistoryData(
        state.workspaceRoute,
        state.opshopSavedHistoryDate,
      );
      return;
    }
    renderWorkspace();
  }

  function updateOpShopTaskPoolView(view) {
    if (!["regular", "oncall", "countryside"].includes(view)) {
      return;
    }
    const route = `opshop/task-pool/${view}`;
    if (state.workspaceRoute === route) {
      return;
    }
    if (typeof navigateWorkspaceRoute === "function") {
      navigateWorkspaceRoute(route);
      return;
    }
    state.workspaceRoute = route;
    state.opshopTaskPoolView = view;
    renderWorkspace();
  }

  function toggleRegularOpShopDateGroup(pickupDate) {
    const scrollSnapshot = captureWindowScroll();
    state.collapsedRegularOpShopPickupDates = toggleCollapsedPickupDateGroup(
      state.collapsedRegularOpShopPickupDates || {},
      pickupDate,
      state.dispatchDate,
    );
    renderWorkspace();
    restoreWindowScroll(scrollSnapshot);
  }

  async function updateOpShopTripSummaryDate(nextDate) {
    state.opshopTripSummaryDate = nextDate || state.dispatchDate;
    if (state.workspaceRoute === "opshop/trip-summary") {
      await loadOpShopRoute(state.workspaceRoute);
      return;
    }
    renderWorkspace();
  }

  async function updateDeliveryTripSummaryDate(nextDate) {
    const deliveryDate = nextDate || state.dispatchDate;
    if (deliveryDate !== state.deliveryTripSummaryDate) {
      clearDeliveryVehicleTransientState();
    }
    state.deliveryTripSummaryDate = deliveryDate;
    if (
      state.workspaceRoute === "delivery/trip-summary"
      || state.workspaceRoute === "delivery/run-sheet"
    ) {
      await loadDeliveryRoute(state.workspaceRoute);
      return;
    }
    renderWorkspace();
  }

  function updateDeliveryTaskPoolFilter(field, value) {
    state.deliveryTaskPoolFilters = {
      ...(state.deliveryTaskPoolFilters || {}),
      [field]: value,
    };
    renderWorkspace();
  }

  function clearDeliveryTaskPoolFilters() {
    state.deliveryTaskPoolFilters = {
      search: "",
      delivery_date: "",
      urgency: "All",
    };
    renderWorkspace();
  }

  function openDeliveryOrderDetail(orderId, { readOnly = false } = {}) {
    state.deliveryOrderDetailId = orderId || "";
    state.deliveryOrderDetailReadOnly = Boolean(readOnly);
    state.deliveryOrderFormMode = "";
    state.deliveryOrderForm = {};
    state.deliveryOrderModalError = "";
    renderWorkspace();
  }

  function closeDeliveryOrderModal() {
    if (state.deliveryOrderFormMode && !confirmAction("Discard unsaved Delivery Order changes?")) {
      return;
    }
    const restoreOrderDetailTriggerId = state.deliveryOrderDetailReadOnly
      ? state.deliveryOrderDetailId
      : "";
    state.deliveryOrderDetailId = "";
    state.deliveryOrderDetailReadOnly = false;
    state.deliveryOrderFormMode = "";
    state.deliveryOrderForm = {};
    state.deliveryOrderModalError = "";
    renderWorkspace();
    focusDeliveryOrderDetailTrigger(restoreOrderDetailTriggerId);
  }

  function openAddDeliveryOrder() {
    state.deliveryOrderDetailId = "";
    state.deliveryOrderDetailReadOnly = false;
    state.deliveryOrderFormMode = "add";
    state.deliveryOrderForm = defaultDeliveryOrderForm();
    state.deliveryOrderModalError = "";
    renderWorkspace();
  }

  function startEditDeliveryOrder(orderId) {
    const order = findDeliveryOrder(orderId);
    if (!order) {
      state.deliveryOrderModalError = "Delivery Order is no longer available.";
      renderWorkspace();
      return;
    }
    state.deliveryOrderDetailId = orderId;
    state.deliveryOrderDetailReadOnly = false;
    state.deliveryOrderFormMode = "edit";
    state.deliveryOrderForm = deliveryOrderFormFromOrder(order);
    state.deliveryOrderModalError = "";
    renderWorkspace();
  }

  function cancelDeliveryOrderEdit() {
    if (!confirmAction("Discard unsaved Delivery Order changes?")) {
      return;
    }
    state.deliveryOrderFormMode = "";
    state.deliveryOrderForm = {};
    state.deliveryOrderModalError = "";
    renderWorkspace();
  }

  function updateDeliveryOrderForm(field, value) {
    state.deliveryOrderForm = {
      ...(state.deliveryOrderForm || {}),
      [field]: value,
    };
  }

  function addDeliveryOrderProductLine() {
    state.deliveryOrderForm = {
      ...(state.deliveryOrderForm || {}),
      product_lines: [
        ...((state.deliveryOrderForm || {}).product_lines || []),
        { product_name: "", quantity: 0, unit: "PALLETS" },
      ],
    };
    renderWorkspace();
  }

  function updateDeliveryOrderProductLine(index, field, value) {
    const lines = [...((state.deliveryOrderForm || {}).product_lines || [])];
    lines[index] = {
      ...(lines[index] || { product_name: "", quantity: 0, unit: "PALLETS" }),
      [field]: field === "quantity" ? Number(value || 0) : value,
    };
    state.deliveryOrderForm = {
      ...(state.deliveryOrderForm || {}),
      product_lines: lines,
    };
  }

  function removeDeliveryOrderProductLine(index) {
    state.deliveryOrderForm = {
      ...(state.deliveryOrderForm || {}),
      product_lines: ((state.deliveryOrderForm || {}).product_lines || []).filter(
        (_line, lineIndex) => lineIndex !== index,
      ),
    };
    renderWorkspace();
  }

  async function saveDeliveryOrderForm() {
    const mode = state.deliveryOrderFormMode;
    const orderId = state.deliveryOrderDetailId;
    const payload = deliveryOrderPayload(state.deliveryOrderForm || {});
    const actionKey = mode === "edit"
      ? `delivery-order-edit:${orderId}`
      : "delivery-order-add";
    await runDeliveryAction(actionKey, async (context) => {
      if (mode === "edit") {
        await api.updateDeliveryOrder(orderId, payload);
      } else {
        await api.createDeliveryOrder(payload);
      }
      if (isDeliveryMutationCurrent(context)) {
        state.deliveryOrderDetailId = "";
        state.deliveryOrderDetailReadOnly = false;
        state.deliveryOrderFormMode = "";
        state.deliveryOrderForm = {};
        state.deliveryOrderModalError = "";
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliveryOrderModalError = `Unable to save Delivery Order. ${error.message}`;
    });
  }

  async function cancelActiveDeliveryOrder(orderId) {
    if (!confirmAction("Cancel this Delivery Order? It will disappear from the active Task Pool.")) {
      return;
    }
    await runDeliveryAction(`delivery-order-cancel:${orderId}`, async (context) => {
      await api.cancelDeliveryOrder(orderId);
      if (isDeliveryMutationCurrent(context)) {
        state.deliveryOrderDetailId = "";
        state.deliveryOrderDetailReadOnly = false;
        state.deliveryOrderFormMode = "";
        state.deliveryOrderForm = {};
        state.deliveryOrderModalError = "";
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliveryOrderModalError = `Unable to cancel Delivery Order. ${error.message}`;
    });
  }

  function openDeliveryAttacheImport() {
    invalidateDeliveryAttachePreview();
    state.deliveryAttacheImportState = {
      ...defaultDeliveryAttacheImportState(),
      isOpen: true,
    };
    renderWorkspace();
  }

  function closeDeliveryAttacheImport() {
    if (hasDeliveryAttacheDraft() && !confirmAction("Discard the current Attaché invoice import?")) {
      return;
    }
    invalidateDeliveryAttachePreview();
    state.deliveryAttacheImportState = defaultDeliveryAttacheImportState();
    renderWorkspace();
  }

  function updateDeliveryAttacheImportFiles(files, { source = "chooser" } = {}) {
    invalidateDeliveryAttachePreview();
    const selectedFiles = Array.from(files || []);
    const pdfFiles = selectedFiles.filter(isPdfFile);
    const rejectedCount = selectedFiles.length - pdfFiles.length;
    let error = "";
    if (selectedFiles.length && !pdfFiles.length) {
      error = source === "drop"
        ? "No PDF files were dropped. Drop one or more PDF files."
        : "No PDF files were selected. Choose one or more PDF files.";
    } else if (rejectedCount) {
      error = `${rejectedCount} non-PDF file${rejectedCount === 1 ? " was" : "s were"} ignored.`;
    }
    state.deliveryAttacheImportState = {
      ...state.deliveryAttacheImportState,
      files: pdfFiles,
      rows: [],
      step: "files",
      expandedRowIds: {},
      error,
      success: "",
    };
    renderWorkspace();
  }

  function removeDeliveryAttacheImportFile(index) {
    invalidateDeliveryAttachePreview();
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      files: (current.files || []).filter((_file, fileIndex) => fileIndex !== index),
      rows: [],
      step: "files",
      expandedRowIds: {},
      error: "",
      success: "",
    };
    renderWorkspace();
  }

  async function previewDeliveryAttacheImport() {
    const importState = state.deliveryAttacheImportState || {};
    if (importState.isPreviewing || !(importState.files || []).length) {
      return;
    }
    const context = captureMutationContext();
    const requestVersion = ++deliveryAttachePreviewRequestVersion;
    const isCurrent = () =>
      isDeliveryMutationCurrent(context) &&
      state.workspaceRoute === "delivery/task-pool" &&
      state.deliveryAttacheImportState?.isOpen &&
      requestVersion === deliveryAttachePreviewRequestVersion;
    state.deliveryAttacheImportState = {
      ...importState,
      isPreviewing: true,
      step: "files",
      error: "",
      success: "",
    };
    renderWorkspace();
    try {
      const response = await api.previewDeliveryAttacheInvoices(importState.files);
      if (!isCurrent()) {
        return;
      }
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        step: "review",
        rows: (response.rows || []).map((row) => ({
          ...row,
          selected: Boolean(row.selected && row.importable && !row.is_duplicate),
        })),
        expandedRowIds: {},
      };
    } catch (error) {
      if (!isCurrent()) {
        return;
      }
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        error: `Unable to preview Attache invoices. ${error.message}`,
      };
    } finally {
      if (isCurrent()) {
        state.deliveryAttacheImportState = {
          ...state.deliveryAttacheImportState,
          isPreviewing: false,
        };
        renderWorkspace();
      }
    }
  }

  function backDeliveryAttacheImportToFiles() {
    invalidateDeliveryAttachePreview();
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      step: "files",
      rows: [],
      expandedRowIds: {},
      error: "",
      success: "",
    };
    renderWorkspace();
  }

  function updateDeliveryAttacheImportRow(rowId, field, value) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) =>
        row.row_id === rowId ? { ...row, [field]: value } : row,
      ),
    };
  }

  function updateDeliveryAttacheImportProductLine(rowId, lineIndex, field, value) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId) {
          return row;
        }
        const productLines = [...(row.product_lines || [])];
        productLines[lineIndex] = {
          ...(productLines[lineIndex] || { product_name: "", quantity: 0, unit: "PALLETS" }),
          [field]: field === "quantity" ? Number(value || 0) : value,
        };
        return { ...row, product_lines: productLines };
      }),
    };
  }

  function addDeliveryAttacheImportProductLine(rowId) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId) {
          return row;
        }
        return {
          ...row,
          product_lines: [
            ...(row.product_lines || []),
            { product_name: "", quantity: 0, unit: "PALLETS" },
          ],
        };
      }),
    };
    renderWorkspace();
  }

  function removeDeliveryAttacheImportProductLine(rowId, lineIndex) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId) {
          return row;
        }
        return {
          ...row,
          product_lines: (row.product_lines || []).filter(
            (_line, index) => index !== lineIndex,
          ),
        };
      }),
    };
    renderWorkspace();
  }

  function toggleDeliveryAttacheImportRow(rowId, selected) {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => {
        if (row.row_id !== rowId || row.is_duplicate || !row.importable) {
          return row;
        }
        return { ...row, selected };
      }),
    };
    renderWorkspace();
  }

  function toggleDeliveryAttacheImportExpanded(rowId) {
    const current = state.deliveryAttacheImportState || {};
    const expandedRowIds = { ...(current.expandedRowIds || {}) };
    if (expandedRowIds[rowId]) {
      delete expandedRowIds[rowId];
    } else {
      expandedRowIds[rowId] = true;
    }
    state.deliveryAttacheImportState = {
      ...current,
      expandedRowIds,
    };
    renderWorkspace();
  }

  function selectAllReadyDeliveryAttacheRows() {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({
        ...row,
        selected: Boolean(row.importable && !row.is_duplicate),
      })),
    };
    renderWorkspace();
  }

  function clearDeliveryAttacheImportSelection() {
    const current = state.deliveryAttacheImportState || {};
    state.deliveryAttacheImportState = {
      ...current,
      rows: (current.rows || []).map((row) => ({ ...row, selected: false })),
    };
    renderWorkspace();
  }

  async function commitDeliveryAttacheImport() {
    const importState = state.deliveryAttacheImportState || {};
    const selectedRows = (importState.rows || []).filter((row) => row.selected);
    if (!selectedRows.length) {
      state.deliveryAttacheImportState = {
        ...importState,
        error: "Select at least one non-duplicate invoice to import.",
      };
      renderWorkspace();
      return;
    }
    await runDeliveryAction("delivery-attache-import", async (context) => {
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        isCommitting: true,
        error: "",
        success: "",
      };
      renderWorkspace();
      const response = await api.commitDeliveryAttacheInvoices({
        rows: state.deliveryAttacheImportState.rows || [],
      });
      if (isDeliveryMutationCurrent(context) && state.deliveryAttacheImportState?.isOpen) {
        state.deliveryAttacheImportState = {
          ...state.deliveryAttacheImportState,
          isCommitting: false,
          rows: (state.deliveryAttacheImportState.rows || []).map((row) =>
            row.selected ? { ...row, selected: false } : row,
          ),
          success:
            `Imported ${response.imported_count || 0} Delivery Orders. `
            + `${response.skipped_count || 0} rows skipped.`,
        };
        await loadDeliveryRoute(context.route);
      }
    }, (error) => {
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        isCommitting: false,
        error: `Unable to import Attache invoices. ${error.message}`,
      };
    });
  }

  async function openDeliverySpecifications() {
    deliverySpecificationRequestVersion += 1;
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
    deliverySpecificationRequestVersion += 1;
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
    const requestVersion = deliverySpecificationRequestVersion;
    const isCurrent = () =>
      isDeliveryMutationCurrent(context) &&
      state.workspaceRoute === "delivery/task-pool" &&
      state.deliverySpecificationModalOpen &&
      requestVersion === deliverySpecificationRequestVersion;
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
    if (!draft.driver_id || !draft.trip_no) {
      state.deliveryActionError = "Select a Driver and Trip before assigning this Delivery Order.";
      renderWorkspace();
      return;
    }
    await runDeliveryAction(`delivery-assignment:${orderId}`, async (context) => {
      const updatedBoard = await api.assignDeliveryWorkspaceOrder({
        dispatch_date: context.dispatchDate,
        order_id: orderId,
        driver_id: draft.driver_id,
        trip_no: draft.trip_no || "trip1",
      });
      if (isDeliveryMutationCurrent(context)) {
        state.deliveryBoard = updatedBoard;
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        pruneDeliveryDrafts();
        renderDeliveryWorkspacePreservingScroll();
      }
    }, null, { preserveScroll: true });
  }

  async function moveDeliveryOrderToTrip(orderId, driverId, tripNo) {
    await runDeliveryAction(`delivery-move:${orderId}:${tripNo}`, async (context) => {
      const updatedBoard = await api.assignDeliveryWorkspaceOrder({
        dispatch_date: context.dispatchDate,
        order_id: orderId,
        driver_id: driverId,
        trip_no: tripNo,
      });
      if (isDeliveryMutationCurrent(context)) {
        state.deliveryBoard = updatedBoard;
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        pruneDeliveryDrafts();
        renderDeliveryWorkspacePreservingScroll();
      }
    }, null, { preserveScroll: true });
  }

  async function unassignDeliveryOrder(orderId) {
    await runDeliveryAction(`delivery-unassign:${orderId}`, async (context) => {
      const updatedBoard = await api.unassignDeliveryWorkspaceOrder({
        dispatch_date: context.dispatchDate,
        order_id: orderId,
      });
      if (isDeliveryMutationCurrent(context)) {
        state.deliveryBoard = updatedBoard;
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        pruneDeliveryDrafts();
        renderDeliveryWorkspacePreservingScroll();
      }
    }, null, { preserveScroll: true });
  }

  async function updateDeliveryVehicleSelection(deliveryDate, driverId, vehicleId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    state.deliveryVehicleDrafts = {
      ...(state.deliveryVehicleDrafts || {}),
      [key]: vehicleId,
    };
    updateDeliveryVehicleClaim(key, vehicleId);
    clearDeliveryVehicleError(key);
    renderWorkspace();
    const currentAssignment = (state.deliveryBoard?.driver_vehicle_assignments || []).find(
      (assignment) =>
        assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
    );
    const conflictDriverNames = getDeliveryVehicleConflictDriverNames({
      board: state.deliveryBoard,
      claims: state.deliveryVehicleClaims,
      deliveryDate,
      driverId,
      vehicleId,
    });
    if (conflictDriverNames.length) {
      renderWorkspace();
      return;
    }
    if (
      !vehicleId
      && !currentAssignment
      && !deliveryVehicleQueues.has(key)
      && !deliveryVehiclePhysicalTails.has(key)
    ) {
      removeDeliveryVehicleDraft(key);
      renderWorkspace();
      retryAvailableDeliveryVehicleClaims(key);
      return;
    }
    return queueDeliveryVehicleUpdate(deliveryDate, driverId);
  }

  function queueDeliveryVehicleUpdate(deliveryDate, driverId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    const existingEntry = deliveryVehicleQueues.get(key);
    if (existingEntry?.mutationVersion === deliveryVehicleMutationVersion) {
      return existingEntry.promise;
    }
    const entry = {
      queueId: ++deliveryVehicleQueueIdCounter,
      mutationVersion: deliveryVehicleMutationVersion,
      dispatchDate: state.dispatchDate,
      deliveryDate,
      promise: null,
    };
    state.deliveryVehiclePendingKeys = {
      ...(state.deliveryVehiclePendingKeys || {}),
      [key]: true,
    };
    renderWorkspace();
    deliveryVehicleQueues.set(key, entry);
    entry.promise = enqueueDeliveryVehiclePhysicalWrite(
      key,
      () => processDeliveryVehicleQueue(entry, deliveryDate, driverId),
    )
      .catch((error) => {
        if (isDeliveryVehicleQueueCurrent(key, entry)) {
          state.deliveryVehicleErrors = {
            ...(state.deliveryVehicleErrors || {}),
            [key]: error.message || "Unable to update Vehicle.",
          };
        }
      })
      .finally(() => {
        if (deliveryVehicleQueues.get(key) !== entry) {
          return;
        }
        deliveryVehicleQueues.delete(key);
        const { [key]: _removed, ...remaining } = state.deliveryVehiclePendingKeys || {};
        state.deliveryVehiclePendingKeys = remaining;
        if (
          entry.mutationVersion === deliveryVehicleMutationVersion
          && state.isLoggedIn
          && state.activeWorkspace === "delivery"
          && state.workspaceRoute === "delivery/trip-summary"
        ) {
          renderWorkspace();
        }
      });
    return entry.promise;
  }

  function enqueueDeliveryVehiclePhysicalWrite(key, operation) {
    const previousTail = deliveryVehiclePhysicalTails.get(key);
    const operationPromise = previousTail
      ? previousTail.catch(() => {}).then(operation)
      : Promise.resolve(operation());
    const settledTail = operationPromise.catch(() => {});
    deliveryVehiclePhysicalTails.set(key, settledTail);
    settledTail.finally(() => {
      if (deliveryVehiclePhysicalTails.get(key) === settledTail) {
        deliveryVehiclePhysicalTails.delete(key);
      }
    });
    return operationPromise;
  }

  async function processDeliveryVehicleQueue(entry, deliveryDate, driverId) {
    const key = deliveryVehicleKey(deliveryDate, driverId);
    while (
      isDeliveryVehicleQueueCurrent(key, entry)
      && Object.prototype.hasOwnProperty.call(state.deliveryVehicleDrafts || {}, key)
    ) {
      const vehicleId = state.deliveryVehicleDrafts[key];
      const conflicts = getDeliveryVehicleConflictDriverNames({
        board: currentDeliveryBoard(),
        claims: state.deliveryVehicleClaims,
        deliveryDate,
        driverId,
        vehicleId,
      });
      if (conflicts.length) {
        return;
      }
      const currentAssignment = (currentDeliveryBoard()?.driver_vehicle_assignments || []).find(
        (assignment) =>
          assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
      );
      if (currentAssignment?.vehicle_id === vehicleId) {
        removeDeliveryVehicleDraft(key);
        removeDeliveryVehicleClaim(key);
        clearDeliveryVehicleError(key);
        return;
      }
      const context = {
        ...captureMutationContext(),
        deliveryDate: state.deliveryTripSummaryDate,
      };
      let updatedBoard;
      try {
        updatedBoard = vehicleId
          ? await api.assignDeliveryWorkspaceVehicle({
            dispatch_date: context.dispatchDate,
            delivery_date: deliveryDate,
            driver_id: driverId,
            vehicle_id: vehicleId,
          })
          : await api.clearDeliveryWorkspaceVehicle({
            dispatch_date: context.dispatchDate,
            delivery_date: deliveryDate,
            driver_id: driverId,
          });
      } catch (error) {
        if (!isDeliveryVehicleQueueCurrent(key, entry)) {
          return;
        }
        if (await handleWorkspaceMigrationGuard(error)) {
          return;
        }
        if (state.deliveryVehicleDrafts?.[key] === vehicleId) {
          state.deliveryVehicleErrors = {
            ...(state.deliveryVehicleErrors || {}),
            [key]: error.message,
          };
          return;
        }
        continue;
      }
      if (!isDeliveryVehicleQueueCurrent(key, entry)) {
        return;
      }
      applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId);
      if (state.deliveryVehicleDrafts?.[key] === vehicleId) {
        removeDeliveryVehicleDraft(key);
        removeDeliveryVehicleClaim(key);
        clearDeliveryVehicleError(key);
        retryAvailableDeliveryVehicleClaims(key);
        return;
      }
    }
  }

  function retryAvailableDeliveryVehicleClaims(excludedKey) {
    Object.entries(state.deliveryVehicleClaims || {})
      .sort((left, right) => Number(left[1].sequence) - Number(right[1].sequence))
      .forEach(([key, claim]) => {
        if (!claim?.vehicle_id || key === excludedKey || deliveryVehicleQueues.has(key)) {
          return;
        }
        const separatorIndex = key.indexOf("|");
        if (separatorIndex < 0) {
          return;
        }
        const deliveryDate = key.slice(0, separatorIndex);
        const driverId = key.slice(separatorIndex + 1);
        const conflicts = getDeliveryVehicleConflictDriverNames({
          board: currentDeliveryBoard(),
          claims: state.deliveryVehicleClaims,
          deliveryDate,
          driverId,
          vehicleId: claim.vehicle_id,
        });
        if (!conflicts.length) {
          queueDeliveryVehicleUpdate(deliveryDate, driverId);
        }
      });
  }

  function isDeliveryVehicleQueueCurrent(key, entry) {
    return (
      deliveryVehicleQueues.get(key) === entry
      && entry.mutationVersion === deliveryVehicleMutationVersion
      && state.isLoggedIn
      && state.workspaceRoute === "delivery/trip-summary"
      && state.activeWorkspace === "delivery"
      && state.dispatchDate === entry.dispatchDate
      && (state.deliveryTripSummaryDate || entry.deliveryDate) === entry.deliveryDate
    );
  }

  function updateDeliveryVehicleClaim(key, vehicleId) {
    if (!vehicleId) {
      removeDeliveryVehicleClaim(key);
      return;
    }
    const existing = state.deliveryVehicleClaims?.[key];
    if (existing?.vehicle_id === vehicleId) {
      return;
    }
    state.deliveryVehicleClaimSequence = Number(state.deliveryVehicleClaimSequence || 0) + 1;
    state.deliveryVehicleClaims = {
      ...(state.deliveryVehicleClaims || {}),
      [key]: {
        vehicle_id: vehicleId,
        sequence: state.deliveryVehicleClaimSequence,
      },
    };
  }

  function removeDeliveryVehicleDraft(key) {
    const { [key]: _removed, ...remaining } = state.deliveryVehicleDrafts || {};
    state.deliveryVehicleDrafts = remaining;
  }

  function removeDeliveryVehicleClaim(key) {
    const { [key]: _removed, ...remaining } = state.deliveryVehicleClaims || {};
    state.deliveryVehicleClaims = remaining;
  }

  function clearDeliveryVehicleError(key) {
    const { [key]: _removed, ...remaining } = state.deliveryVehicleErrors || {};
    state.deliveryVehicleErrors = remaining;
  }

  function applyDeliveryVehicleBoardUpdate(updatedBoard, deliveryDate, driverId) {
    if (!updatedBoard) {
      return;
    }
    const targetBoard = currentDeliveryBoard();
    const otherAssignments = (targetBoard?.driver_vehicle_assignments || []).filter(
      (assignment) =>
        assignment.delivery_date !== deliveryDate || assignment.driver_id !== driverId,
    );
    const updatedAssignment = (updatedBoard.driver_vehicle_assignments || []).filter(
      (assignment) =>
        assignment.delivery_date === deliveryDate && assignment.driver_id === driverId,
    );
    const nextBoard = {
      ...(targetBoard || {}),
      driver_vehicle_assignments: otherAssignments.concat(updatedAssignment),
    };
    if (state.workspaceRoute === "delivery/trip-summary" && state.deliveryTripSummaryBoard) {
      state.deliveryTripSummaryBoard = nextBoard;
    } else {
      state.deliveryBoard = nextBoard;
    }
  }

  function generateDeliveryRunSheet(candidate) {
    if (!candidate || !(candidate.orders || []).length) {
      return;
    }
    state.deliveryGenerationConfirmation = {
      ...candidate,
      dispatch_date: state.dispatchDate,
      error: "",
      orders: (candidate.orders || []).map((order) => ({ ...order })),
      totals: { ...(candidate.totals || {}) },
      vehicle: candidate.vehicle ? { ...candidate.vehicle } : null,
    };
    state.deliveryActionError = "";
    renderWorkspace();
  }

  function closeDeliveryGenerationConfirmation() {
    const confirmation = state.deliveryGenerationConfirmation;
    if (!confirmation || isDeliveryGenerationBusy(confirmation)) {
      return;
    }
    state.deliveryGenerationConfirmation = null;
    renderWorkspace();
    restoreGenerateButtonFocus("delivery", confirmation);
  }

  async function confirmGenerateDeliveryRunSheet() {
    const candidate = state.deliveryGenerationConfirmation;
    if (!candidate || isDeliveryGenerationBusy(candidate)) {
      return;
    }
    await runDeliveryAction(
      `delivery-generate:${candidate.delivery_date}:${candidate.driver_id}`,
      async (context) => {
        await api.createGeneratedDeliveryRunSheet({
          dispatch_date: context.dispatchDate,
          delivery_date: candidate.delivery_date,
          driver_id: candidate.driver_id,
        });
        if (isDeliveryMutationCurrent(context)) {
          state.deliveryGenerationConfirmation = null;
          await navigateToDeliveryRunSheets();
        }
      },
      (error) => {
        state.deliveryGenerationConfirmation = {
          ...candidate,
          error: error.message,
        };
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

  async function exportDeliveryRunSheets(deliveryDate) {
    const scopedDate = deliveryDate || state.deliveryTripSummaryDate || state.dispatchDate;
    const actionKey = `delivery-export-date:${scopedDate}`;
    if (state.deliveryBusyActionKeys?.[actionKey]) {
      return;
    }
    await runDeliveryAction(actionKey, async () => {
      await api.exportDeliveryRunSheetsExcel(scopedDate);
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

  function generateOpShopPickupCollection(candidate) {
    if (!candidate || !(candidate.pickups || []).length) {
      return;
    }
    state.opshopGenerationConfirmation = {
      ...candidate,
      dispatch_date: state.dispatchDate,
      error: "",
      pickups: (candidate.pickups || []).map((pickup) => ({ ...pickup })),
    };
    state.opshopActionError = "";
    renderWorkspace();
  }

  function closeOpShopGenerationConfirmation() {
    const confirmation = state.opshopGenerationConfirmation;
    if (!confirmation || isOpShopGenerationBusy(confirmation)) {
      return;
    }
    state.opshopGenerationConfirmation = null;
    renderWorkspace();
    restoreGenerateButtonFocus("opshop", confirmation);
  }

  async function confirmGenerateOpShopPickupCollection() {
    const candidate = state.opshopGenerationConfirmation;
    if (!candidate || isOpShopGenerationBusy(candidate)) {
      return;
    }
    await runOpShopAction(
      `opshop-generate:${candidate.pickup_date}:${candidate.driver_id}`,
      async (context) => {
        await api.createGeneratedOpShopPickupCollection({
          dispatch_date: context.dispatchDate,
          pickup_date: candidate.pickup_date,
          driver_id: candidate.driver_id,
        });
        if (isOpShopMutationCurrent(context)) {
          state.opshopGenerationConfirmation = null;
          await loadOpShopRoute(context.route);
        }
      },
      async (error, context) => {
        await loadOpShopRoute(context.route);
        if (isOpShopMutationCurrent(context)) {
          state.opshopGenerationConfirmation = {
            ...candidate,
            error: error.message,
          };
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

  async function exportOpShopPickupCollections(pickupDate) {
    const scopedDate = pickupDate || state.opshopTripSummaryDate || state.dispatchDate;
    const actionKey = `opshop-export-date:${scopedDate}`;
    if (state.opshopBusyActionKeys?.[actionKey]) {
      return;
    }
    await runOpShopAction(actionKey, async (context) => {
      await api.exportOpShopPickupCollectionsExcel({
        pickupDate: scopedDate,
        dispatchDate: context.dispatchDate,
      });
    });
  }

  async function runDeliveryAction(
    actionKey,
    callback,
    onError = null,
    { preserveScroll = false } = {},
  ) {
    const context = captureMutationContext();
    const token = nextActionToken();
    state.deliveryBusyActionKeys = state.deliveryBusyActionKeys || {};
    setBusyAction(state.deliveryBusyActionKeys, actionKey, token);
    state.deliveryActionError = "";
    if (preserveScroll) {
      renderDeliveryWorkspacePreservingScroll();
    } else {
      renderWorkspace();
    }
    try {
      await callback(context);
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      if (isDeliveryMutationCurrent(context)) {
        if (typeof onError === "function") {
          onError(error);
        } else {
          state.deliveryActionError = error.message;
        }
      }
    } finally {
      if (clearBusyAction(state.deliveryBusyActionKeys, actionKey, token)) {
        if (!preserveScroll || isDeliveryMutationCurrent(context)) {
          if (preserveScroll) {
            renderDeliveryWorkspacePreservingScroll();
          } else {
            renderWorkspace();
          }
        }
      }
    }
  }

  async function runOpShopAction(actionKey, callback, onError = null) {
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
        if (typeof onError === "function") {
          await onError(error, context);
        } else {
          state.opshopActionError = error.message;
        }
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

  function renderDeliveryWorkspacePreservingScroll() {
    if (
      typeof window === "undefined"
      || typeof window.requestAnimationFrame !== "function"
      || typeof window.scrollTo !== "function"
    ) {
      renderWorkspace();
      return;
    }
    const scrollX = Number(window.scrollX || 0);
    const scrollY = Number(window.scrollY || 0);
    renderWorkspace();
    window.requestAnimationFrame(() => window.scrollTo(scrollX, scrollY));
  }

  function findDeliveryAssignment(orderId) {
    return (currentDeliveryBoard()?.assignments || []).find(
      (assignment) => assignment.task_id === orderId,
    );
  }

  function findDeliveryOrder(orderId) {
    return (currentDeliveryBoard()?.orders || []).find(
      (order) => order.order_id === orderId,
    );
  }

  function currentDeliveryBoard() {
    return state.workspaceRoute === "delivery/trip-summary"
      ? state.deliveryTripSummaryBoard || state.deliveryBoard
      : state.deliveryBoard;
  }

  function pruneDeliveryDrafts() {
    const orderIds = new Set((state.deliveryBoard?.orders || []).map((order) => order.order_id));
    state.deliveryAssignmentDrafts = Object.fromEntries(
      Object.entries(state.deliveryAssignmentDrafts || {}).filter(([orderId]) =>
        orderIds.has(orderId),
      ),
    );
    pruneDeliveryVehicleDrafts(state.deliveryBoard);
  }

  function pruneDeliveryVehicleDrafts(board = state.deliveryBoard) {
    const vehicleKeys = new Set();
    (board?.driver_vehicle_assignments || []).forEach((assignment) => {
      vehicleKeys.add(deliveryVehicleKey(assignment.delivery_date, assignment.driver_id));
    });
    (board?.assignments || []).forEach((assignment) => {
      const order = (board?.orders || []).find(
        (item) => item.order_id === assignment.task_id,
      );
      if (order?.delivery_date) {
        vehicleKeys.add(deliveryVehicleKey(order.delivery_date, assignment.driver_id));
      }
    });
    (board?.drivers || []).forEach((driver) => {
      vehicleKeys.add(deliveryVehicleKey(
        state.deliveryTripSummaryDate || state.dispatchDate,
        driver.driver_id,
      ));
    });
    state.deliveryVehicleDrafts = Object.fromEntries(
      Object.entries(state.deliveryVehicleDrafts || {}).filter(([key, vehicleId]) => {
        if (!vehicleKeys.has(key)) {
          return false;
        }
        const separatorIndex = key.indexOf("|");
        const deliveryDate = key.slice(0, separatorIndex);
        const driverId = key.slice(separatorIndex + 1);
        return !(board?.driver_vehicle_assignments || []).some(
          (assignment) =>
            assignment.delivery_date === deliveryDate
            && assignment.driver_id === driverId
            && assignment.vehicle_id === vehicleId,
        );
      }),
    );
    state.deliveryVehicleClaims = Object.fromEntries(
      Object.entries(state.deliveryVehicleClaims || {}).filter(([key, claim]) =>
        vehicleKeys.has(key)
        && state.deliveryVehicleDrafts?.[key] === claim?.vehicle_id,
      ),
    );
    state.deliveryVehicleErrors = Object.fromEntries(
      Object.entries(state.deliveryVehicleErrors || {}).filter(([key]) =>
        vehicleKeys.has(key),
      ),
    );
    state.deliveryVehiclePendingKeys = Object.fromEntries(
      Object.entries(state.deliveryVehiclePendingKeys || {}).filter(([key]) =>
        vehicleKeys.has(key) && deliveryVehicleQueues.has(key),
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
    invalidateDeliveryAttachePreview();
    state.deliveryTripSummaryBoard = null;
    state.deliveryTripSummaryRunSheets = [];
    state.deliveryAssignmentDrafts = {};
    clearDeliveryVehicleTransientState();
    state.deliveryOrderDetailId = "";
    state.deliveryOrderDetailReadOnly = false;
    state.deliveryOrderForm = {};
    state.deliveryOrderFormMode = "";
    state.deliveryOrderModalError = "";
    state.deliveryAttacheImportState = defaultDeliveryAttacheImportState();
    state.deliverySpecificationModalOpen = false;
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    state.deliverySpecificationError = "";
    state.deliverySpecificationBusyKey = "";
    state.opshopAssignmentDrafts = {};
    state.opshopTripSummaryBoard = null;
    state.opshopTripSummaryCollections = [];
    state.countrysideRouteGroupDrafts = {};
    state.collapsedRegularOpShopPickupDates = {};
    state.deliveryActionError = "";
    state.opshopActionError = "";
    state.deliveryBusyActionKeys = {};
    state.opshopBusyActionKeys = {};
    state.deliveryGenerationConfirmation = null;
    state.opshopGenerationConfirmation = null;
  }

  function clearGenerationConfirmationsForRoute(route) {
    if (route !== "delivery/trip-summary") {
      state.deliveryGenerationConfirmation = null;
    }
    if (route !== "opshop/trip-summary") {
      state.opshopGenerationConfirmation = null;
    }
  }

  function isDeliveryGenerationBusy(confirmation) {
    return Boolean(state.deliveryBusyActionKeys?.[
      `delivery-generate:${confirmation.delivery_date}:${confirmation.driver_id}`
    ]);
  }

  function isOpShopGenerationBusy(confirmation) {
    return Boolean(state.opshopBusyActionKeys?.[
      `opshop-generate:${confirmation.pickup_date}:${confirmation.driver_id}`
    ]);
  }

  function restoreGenerateButtonFocus(workspace, confirmation) {
    if (
      typeof document === "undefined"
      || typeof window === "undefined"
      || typeof window.requestAnimationFrame !== "function"
    ) {
      return;
    }
    window.requestAnimationFrame(() => {
      const button = Array.from(
        document.querySelectorAll(`[data-workspace-generate="${workspace}"]`),
      ).find(
        (item) =>
          item.dataset.driverId === confirmation.driver_id
          && item.dataset.serviceDate === (
            confirmation.delivery_date || confirmation.pickup_date
          ),
      );
      button?.focus();
    });
  }

  function clearDeliveryTaskPoolModals() {
    invalidateDeliveryAttachePreview();
    state.deliveryOrderDetailId = "";
    state.deliveryOrderDetailReadOnly = false;
    state.deliveryOrderForm = {};
    state.deliveryOrderFormMode = "";
    state.deliveryOrderModalError = "";
    state.deliveryAttacheImportState = defaultDeliveryAttacheImportState();
    state.deliverySpecificationModalOpen = false;
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    state.deliverySpecificationError = "";
    state.deliverySpecificationBusyKey = "";
  }

  function focusDeliveryOrderDetailTrigger(orderId) {
    if (!orderId || typeof window === "undefined" || typeof document === "undefined") {
      return;
    }
    const focusTrigger = () => {
      const trigger = Array.from(document.querySelectorAll(".workspace-order-detail-trigger"))
        .find((item) => item.dataset.orderId === orderId);
      if (trigger && typeof trigger.focus === "function") {
        trigger.focus({ preventScroll: true });
      }
    };
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(() => {
        focusTrigger();
        window.requestAnimationFrame(focusTrigger);
      });
    }
    if (typeof window.setTimeout === "function") {
      window.setTimeout(focusTrigger, 0);
      window.setTimeout(focusTrigger, 50);
    }
    focusTrigger();
  }

  function hasDeliveryAttacheDraft() {
    const current = state.deliveryAttacheImportState || {};
    return Boolean(
      current.isOpen &&
      !current.success &&
      ((current.files || []).length || (current.rows || []).length),
    );
  }

  function invalidateDeliveryAttachePreview() {
    deliveryAttachePreviewRequestVersion += 1;
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

  async function navigateToDeliveryRunSheets() {
    if (typeof navigateWorkspaceRoute === "function") {
      await navigateWorkspaceRoute("delivery/run-sheet");
      return;
    }
    state.workspaceRoute = "delivery/run-sheet";
    state.activeWorkspace = "delivery";
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

  function clearDeliveryVehicleTransientState() {
    deliveryVehicleMutationVersion += 1;
    deliveryVehicleQueues.clear();
    state.deliveryVehicleDrafts = {};
    state.deliveryVehicleClaims = {};
    state.deliveryVehicleErrors = {};
    state.deliveryVehiclePendingKeys = {};
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
    addDeliveryAttacheImportProductLine,
    addDeliveryOrderProductLine,
    backDeliveryAttacheImportToFiles,
    cancelActiveDeliveryOrder,
    cancelDeliveryDriverForm,
    applyDeliveryOrderAssignment,
    applyOpShopAssignmentChanges,
    assignCountrysideRouteGroup,
    cancelDeliveryRunSheet,
    cancelDeliveryOrderEdit,
    cancelDeliveryVehicleForm,
    clearDeliveryTaskPoolFilters,
    clearDeliveryAttacheImportSelection,
    cancelOpShopPickupCollection,
    closeDeliveryGenerationConfirmation,
    closeOpShopGenerationConfirmation,
    closeDeliveryAttacheImport,
    closeDeliveryOrderModal,
    closeDeliverySpecifications,
    commitDeliveryAttacheImport,
    deleteDeliveryDriver,
    deleteDeliveryVehicle,
    exportDeliveryRunSheet,
    exportDeliveryRunSheets,
    exportOpShopPickupCollection,
    exportOpShopPickupCollections,
    confirmGenerateDeliveryRunSheet,
    confirmGenerateOpShopPickupCollection,
    generateDeliveryRunSheet,
    generateOpShopPickupCollection,
    loadWorkspaceRoute,
    moveDeliveryOrderToTrip,
    openAddDeliveryOrder,
    openDeliveryAttacheImport,
    openDeliveryOrderDetail,
    openDeliverySpecifications,
    previewDeliveryAttacheImport,
    resetDeliveryVehicleTransientState: clearDeliveryVehicleTransientState,
    removeDeliveryOrderProductLine,
    removeDeliveryAttacheImportProductLine,
    removeDeliveryAttacheImportFile,
    saveDeliveryRunSheet,
    saveDeliveryDriver,
    saveDeliveryOrderForm,
    saveDeliveryVehicle,
    saveOpShopPickupCollection,
    setDeliverySpecificationTab,
    startAddDeliveryDriver,
    startAddDeliveryVehicle,
    startEditDeliveryDriver,
    startEditDeliveryOrder,
    startEditDeliveryVehicle,
    selectAllReadyDeliveryAttacheRows,
    toggleDeliveryAttacheImportRow,
    toggleDeliveryAttacheImportExpanded,
    toggleDeliveryDriverAvailability,
    toggleDeliveryVehicleAvailability,
    unassignDeliveryOrder,
    unassignOpShopPickup,
    updateCountrysideRouteGroupDraft,
    updateDeliveryAssignmentDraft,
    updateDeliveryAttacheImportFiles,
    updateDeliveryAttacheImportProductLine,
    updateDeliveryAttacheImportRow,
    updateDeliveryDriverForm,
    updateDeliveryOrderForm,
    updateDeliveryOrderProductLine,
    updateDeliverySavedHistoryDate,
    updateDeliveryTaskPoolFilter,
    updateDeliveryTripSummaryDate,
    updateDeliveryVehicleSelection,
    updateDeliveryVehicleForm,
    updateDispatchDate,
    updateOpShopSavedHistoryDate,
    updateOpShopAssignmentDraft,
    updateOpShopTaskPoolView,
    updateOpShopTripSummaryDate,
    toggleRegularOpShopDateGroup,
  };
}


function sortDeliverySavedHistory(runSheets) {
  return (runSheets || [])
    .filter((runSheet) => runSheet.status === "SAVED")
    .slice()
    .sort((left, right) =>
      String(right.delivery_date || "").localeCompare(
        String(left.delivery_date || ""),
      )
      || compareHistoryText(
        left.driver_name_snapshot || left.driver_id,
        right.driver_name_snapshot || right.driver_id,
      )
      || compareHistoryText(left.run_sheet_id, right.run_sheet_id),
    );
}


function sortOpShopSavedHistory(collections) {
  return (collections || [])
    .filter((collection) => collection.status === "SAVED")
    .slice()
    .sort((left, right) =>
      String(right.pickup_date || "").localeCompare(
        String(left.pickup_date || ""),
      )
      || compareHistoryText(
        left.driver_name_snapshot || left.driver_id,
        right.driver_name_snapshot || right.driver_id,
      )
      || compareHistoryText(left.collection_id, right.collection_id),
    );
}


function compareHistoryText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, {
    sensitivity: "base",
  });
}


function defaultDeliveryOrderForm(order = {}) {
  return {
    invoice_number: order.invoice_number || "",
    order_no: order.order_no || "",
    company_name: order.company_name || "",
    phone: order.phone || "",
    delivery_address: order.delivery_address || "",
    suburb: order.suburb || "",
    postcode: order.postcode || "",
    delivery_date: order.delivery_date || "",
    start_time: order.start_time || "",
    end_time: order.end_time || "",
    zone: order.zone || "",
    urgency: order.urgency || "Normal",
    preferred_driver_id: order.preferred_driver_id || "",
    pallet_quantity: String(order.pallet_quantity ?? 0),
    loose_bags_quantity: String(order.loose_bags_quantity ?? 0),
    note: order.note || "",
    product_lines: (order.product_lines || []).map((line) => ({
      product_name: line.product_name || "",
      quantity: Number(line.quantity || 0),
      unit: line.unit || "PALLETS",
    })),
  };
}


function defaultDeliveryAttacheImportState() {
  return {
    isOpen: false,
    isPreviewing: false,
    isCommitting: false,
    step: "files",
    files: [],
    rows: [],
    expandedRowIds: {},
    error: "",
    success: "",
  };
}


function isPdfFile(file) {
  if (!file) {
    return false;
  }
  const name = String(file.name || "").toLowerCase();
  const type = String(file.type || "").toLowerCase();
  return type === "application/pdf" || name.endsWith(".pdf");
}


function deliveryOrderFormFromOrder(order) {
  return defaultDeliveryOrderForm(order);
}


function deliveryOrderPayload(form) {
  return {
    invoice_number: form.invoice_number || null,
    order_no: form.order_no || null,
    company_name: form.company_name || "",
    phone: form.phone || null,
    delivery_address: form.delivery_address || "",
    suburb: form.suburb || "",
    postcode: form.postcode || "",
    delivery_date: form.delivery_date || "",
    start_time: form.start_time || null,
    end_time: form.end_time || null,
    zone: form.zone || "",
    urgency: form.urgency || "Normal",
    preferred_driver_id: form.preferred_driver_id || null,
    pallet_quantity: Number(form.pallet_quantity || 0),
    loose_bags_quantity: Number(form.loose_bags_quantity || 0),
    note: form.note || null,
    product_lines: (form.product_lines || []).map((line) => ({
      product_name: line.product_name || "",
      quantity: Number(line.quantity || 0),
      unit: line.unit || "PALLETS",
    })),
  };
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


function currentOpShopDriverId(pickup) {
  return pickup?.assigned_driver_id || pickup?.driver_id || "";
}


function deliveryVehicleKey(deliveryDate, driverId) {
  return `${deliveryDate || ""}|${driverId || ""}`;
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
