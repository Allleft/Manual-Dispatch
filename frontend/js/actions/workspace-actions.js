import {
  DEFAULT_API,
  createWorkspaceRequestContext,
  defaultConfirmAction,
} from "./workspace/workspace-request-context.js";
import { createWorkspaceAsyncGuards } from "./workspace/workspace-async-guards.js";
import { createWorkspaceStateReset } from "./workspace/workspace-state-reset.js";
import { createWorkspaceBusyActions } from "./workspace/workspace-busy-actions.js";
import { createDeliveryWorkspaceActions } from "./workspace/delivery-workspace-actions.js";
import { createDeliveryTaskPoolActions } from "./workspace/delivery-task-pool-actions.js";
import { createDeliveryTripSummaryActions } from "./workspace/delivery-trip-summary-actions.js";
import { createDeliveryVehicleQueue } from "./workspace/delivery-vehicle-queue.js";
import { createDeliveryRunSheetActions } from "./workspace/delivery-run-sheet-actions.js";
import { createDeliveryHistoryActions } from "./workspace/delivery-history-actions.js";
import { createDeliverySpecificationActions } from "./workspace/delivery-specification-actions.js";
import { createDeliveryAttacheActions } from "./workspace/delivery-attache-actions.js";
import { createOpShopWorkspaceActions } from "./workspace/opshop-workspace-actions.js";
import { createOpShopTaskPoolActions } from "./workspace/opshop-task-pool-actions.js";
import { createOpShopTripSummaryActions } from "./workspace/opshop-trip-summary-actions.js";
import { createOpShopCollectionActions } from "./workspace/opshop-collection-actions.js";
import { createOpShopHistoryActions } from "./workspace/opshop-history-actions.js";
import { createWorkspaceRouteLoaders } from "./workspace/workspace-route-loaders.js";


export function createWorkspaceActions({
  state,
  renderWorkspace,
  api = DEFAULT_API,
  confirmAction = defaultConfirmAction,
  navigateWorkspaceRoute = null,
}) {
  const context = createWorkspaceRequestContext({
    state,
    renderWorkspace,
    api,
    confirmAction,
    navigateWorkspaceRoute,
  });
  Object.assign(context.actions, createWorkspaceAsyncGuards(context));
  Object.assign(context.actions, createWorkspaceStateReset(context));
  Object.assign(context.actions, createWorkspaceBusyActions(context));
  Object.assign(context.actions, createDeliveryWorkspaceActions(context));
  Object.assign(context.actions, createDeliveryTaskPoolActions(context));
  Object.assign(context.actions, createDeliveryTripSummaryActions(context));
  Object.assign(context.actions, createDeliveryVehicleQueue(context));
  Object.assign(context.actions, createDeliveryRunSheetActions(context));
  Object.assign(context.actions, createDeliveryHistoryActions(context));
  Object.assign(context.actions, createDeliverySpecificationActions(context));
  Object.assign(context.actions, createDeliveryAttacheActions(context));
  Object.assign(context.actions, createOpShopWorkspaceActions(context));
  Object.assign(context.actions, createOpShopTaskPoolActions(context));
  Object.assign(context.actions, createOpShopTripSummaryActions(context));
  Object.assign(context.actions, createOpShopCollectionActions(context));
  Object.assign(context.actions, createOpShopHistoryActions(context));
  Object.assign(context.actions, createWorkspaceRouteLoaders(context));

  const {
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
    clearDeliveryVehicleTransientState,
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
  } = context.actions;

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
