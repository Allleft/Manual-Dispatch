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
  apiExportOpShopPickupCollectionExcel,
  apiGetDeliverySpecifications,
  apiGetDeliveryWorkspaceBoard,
  apiGetOpShopWorkspaceBoard,
  apiGetWorkspaceMigrationStatus,
  apiListDeliveryRunSheets,
  apiListOpShopPickupCollections,
  apiPreviewDeliveryAttacheInvoices,
  apiSaveGeneratedDeliveryRunSheet,
  apiSaveGeneratedOpShopPickupCollection,
  apiUnassignDeliveryWorkspaceOrder,
  apiUnassignOpShopWorkspacePickup,
  apiUpdateDeliveryDriver,
  apiUpdateDeliveryOrder,
  apiUpdateDeliveryVehicle,
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
  exportOpShopPickupCollectionExcel: apiExportOpShopPickupCollectionExcel,
  getDeliverySpecifications: apiGetDeliverySpecifications,
  getDeliveryWorkspaceBoard: apiGetDeliveryWorkspaceBoard,
  getOpShopWorkspaceBoard: apiGetOpShopWorkspaceBoard,
  getWorkspaceMigrationStatus: apiGetWorkspaceMigrationStatus,
  listDeliveryRunSheets: apiListDeliveryRunSheets,
  listOpShopPickupCollections: apiListOpShopPickupCollections,
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
    state.deliveryOrderDetailId = "";
    state.deliveryOrderForm = {};
    state.deliveryOrderFormMode = "";
    state.deliveryOrderModalError = "";
    state.deliveryAttacheImportState = {
      isOpen: false,
      isPreviewing: false,
      isCommitting: false,
      files: [],
      rows: [],
      error: "",
      success: "",
    };
    state.deliverySpecificationModalOpen = false;
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    state.deliverySpecificationError = "";
    state.deliverySpecificationBusyKey = "";
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

  function openDeliveryOrderDetail(orderId) {
    state.deliveryOrderDetailId = orderId || "";
    state.deliveryOrderFormMode = "";
    state.deliveryOrderForm = {};
    state.deliveryOrderModalError = "";
    renderWorkspace();
  }

  function closeDeliveryOrderModal() {
    state.deliveryOrderDetailId = "";
    state.deliveryOrderFormMode = "";
    state.deliveryOrderForm = {};
    state.deliveryOrderModalError = "";
    renderWorkspace();
  }

  function openAddDeliveryOrder() {
    state.deliveryOrderDetailId = "";
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
    state.deliveryOrderFormMode = "edit";
    state.deliveryOrderForm = deliveryOrderFormFromOrder(order);
    state.deliveryOrderModalError = "";
    renderWorkspace();
  }

  function cancelDeliveryOrderEdit() {
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
    state.deliveryAttacheImportState = {
      isOpen: true,
      isPreviewing: false,
      isCommitting: false,
      files: [],
      rows: [],
      error: "",
      success: "",
    };
    renderWorkspace();
  }

  function closeDeliveryAttacheImport() {
    state.deliveryAttacheImportState = {
      isOpen: false,
      isPreviewing: false,
      isCommitting: false,
      files: [],
      rows: [],
      error: "",
      success: "",
    };
    renderWorkspace();
  }

  function updateDeliveryAttacheImportFiles(files) {
    state.deliveryAttacheImportState = {
      ...state.deliveryAttacheImportState,
      files: Array.from(files || []),
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
    state.deliveryAttacheImportState = {
      ...importState,
      isPreviewing: true,
      error: "",
      success: "",
    };
    renderWorkspace();
    try {
      const response = await api.previewDeliveryAttacheInvoices(importState.files);
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        rows: (response.rows || []).map((row) => ({
          ...row,
          selected: Boolean(row.selected && row.importable && !row.is_duplicate),
        })),
      };
    } catch (error) {
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        error: `Unable to preview Attache invoices. ${error.message}`,
      };
    } finally {
      state.deliveryAttacheImportState = {
        ...state.deliveryAttacheImportState,
        isPreviewing: false,
      };
      renderWorkspace();
    }
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
      if (isDeliveryMutationCurrent(context)) {
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
    try {
      state.deliverySpecifications = await api.getDeliverySpecifications();
    } catch (error) {
      if (await handleWorkspaceMigrationGuard(error)) {
        return;
      }
      state.deliverySpecificationError =
        `Unable to load Delivery specifications. ${error.message}`;
    } finally {
      renderWorkspace();
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
        if (isDeliveryMutationCurrent(context)) {
          await navigateToDeliveryRunSheets();
        }
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

  async function runDeliveryAction(actionKey, callback, onError = null) {
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
        if (typeof onError === "function") {
          onError(error);
        } else {
          state.deliveryActionError = error.message;
        }
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

  function findDeliveryOrder(orderId) {
    return (state.deliveryBoard?.orders || []).find(
      (order) => order.order_id === orderId,
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
    state.deliveryOrderDetailId = "";
    state.deliveryOrderForm = {};
    state.deliveryOrderFormMode = "";
    state.deliveryOrderModalError = "";
    state.deliveryAttacheImportState = {
      isOpen: false,
      isPreviewing: false,
      isCommitting: false,
      files: [],
      rows: [],
      error: "",
      success: "",
    };
    state.deliverySpecificationModalOpen = false;
    state.deliveryDriverForm = null;
    state.deliveryDriverEditingId = "";
    state.deliveryVehicleForm = null;
    state.deliveryVehicleEditingId = "";
    state.deliverySpecificationError = "";
    state.deliverySpecificationBusyKey = "";
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
    cancelActiveDeliveryOrder,
    cancelDeliveryDriverForm,
    applyDeliveryOrderAssignment,
    applyDeliveryVehicleAssignment,
    addDeliveryOrderToTrip,
    applyOpShopAssignmentChanges,
    assignCountrysideRouteGroup,
    cancelDeliveryRunSheet,
    cancelDeliveryOrderEdit,
    cancelDeliveryVehicleForm,
    clearDeliveryTaskPoolFilters,
    cancelOpShopPickupCollection,
    clearDeliveryVehicleAssignment,
    closeDeliveryAttacheImport,
    closeDeliveryOrderModal,
    closeDeliverySpecifications,
    commitDeliveryAttacheImport,
    deleteDeliveryDriver,
    deleteDeliveryVehicle,
    exportDeliveryRunSheet,
    exportOpShopPickupCollection,
    generateDeliveryRunSheet,
    generateOpShopPickupCollection,
    loadWorkspaceRoute,
    moveDeliveryOrderToTrip,
    openAddDeliveryOrder,
    openDeliveryAttacheImport,
    openDeliveryOrderDetail,
    openDeliverySpecifications,
    previewDeliveryAttacheImport,
    removeDeliveryOrderProductLine,
    removeDeliveryAttacheImportProductLine,
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
    toggleDeliveryAttacheImportRow,
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
    updateDeliveryTaskPoolFilter,
    updateDeliveryTripAddOrderDraft,
    updateDeliveryTripSummaryDate,
    updateDeliveryVehicleDraft,
    updateDeliveryVehicleForm,
    updateDispatchDate,
    updateOpShopAssignmentDraft,
  };
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
