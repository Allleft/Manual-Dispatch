import { updateDeliveryTaskPoolFilteredContent } from "../../render/delivery/delivery-task-pool-renderer.js";
import { captureWindowScroll, restoreWindowScroll } from "../../utils/scroll-utils.js";

let deliveryProductLineDraftSequence = 0;

function nextDeliveryProductLineDraftId() {
  deliveryProductLineDraftSequence += 1;
  return `delivery-product-line-${deliveryProductLineDraftSequence}`;
}

export function createDeliveryTaskPoolActions(context) {
  const {
    api,
    confirmAction,
    navigateWorkspaceRoute,
    renderWorkspace,
    state,
  } = context;

  const loadDeliveryRoute = (...args) => context.actions.loadDeliveryRoute(...args);
  const runDeliveryAction = (...args) => context.actions.runDeliveryAction(...args);
  const renderDeliveryWorkspacePreservingScroll = (...args) => context.actions.renderDeliveryWorkspacePreservingScroll(...args);
  const currentDeliveryBoard = (...args) => context.actions.currentDeliveryBoard(...args);
  const pruneDeliveryVehicleDrafts = (...args) => context.actions.pruneDeliveryVehicleDrafts(...args);
  const invalidateDeliveryAttachePreview = (...args) => context.actions.invalidateDeliveryAttachePreview(...args);
  const dispatchMetadataForContext = (...args) => context.actions.dispatchMetadataForContext(...args);
  const isDeliveryMutationCurrent = (...args) => context.actions.isDeliveryMutationCurrent(...args);
  const defaultDeliveryAttacheImportState = (...args) => context.actions.defaultDeliveryAttacheImportState(...args);

  function updateDeliveryTaskPoolFilter(field, value) {
    state.deliveryTaskPoolFilters = {
      ...(state.deliveryTaskPoolFilters || {}),
      [field]: value,
    };
    if (field === "search") {
      const scrollSnapshot = captureWindowScroll();
      if (updateDeliveryTaskPoolFilteredContent(
        currentDeliveryBoard(),
        state,
        context.actions,
      )) {
        restoreWindowScroll(scrollSnapshot);
        return;
      }
    }
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
        {
          _draft_id: nextDeliveryProductLineDraftId(),
          product_code: "",
          product_name: "",
          quantity: 0,
          unit: "KG",
          package_quantity: "",
          package_unit: "",
        },
      ],
    };
    renderWorkspace();
  }

  function updateDeliveryOrderProductLine(lineId, field, value) {
    const lines = [...((state.deliveryOrderForm || {}).product_lines || [])];
    const index = lines.findIndex((line) => line._draft_id === lineId);
    if (index < 0) {
      return;
    }
    lines[index] = {
      ...(lines[index] || {
        product_code: "",
        product_name: "",
        quantity: 0,
        unit: "KG",
        package_quantity: "",
        package_unit: "",
      }),
      [field]: ["quantity", "package_quantity"].includes(field)
        ? (value === "" ? "" : Number(value))
        : value,
    };
    state.deliveryOrderForm = {
      ...(state.deliveryOrderForm || {}),
      product_lines: lines,
    };
  }

  function removeDeliveryOrderProductLine(lineId) {
    state.deliveryOrderForm = {
      ...(state.deliveryOrderForm || {}),
      product_lines: ((state.deliveryOrderForm || {}).product_lines || []).filter(
        (line) => line._draft_id !== lineId,
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
        ...dispatchMetadataForContext(context),
        order_id: orderId,
        driver_id: draft.driver_id,
        trip_no: draft.trip_no || "trip1",
      });
      if (isDeliveryMutationCurrent(context)) {
        if (context.route === "delivery/trip-summary") {
          state.deliveryTripSummaryBoard = updatedBoard;
          pruneDeliveryVehicleDrafts(updatedBoard);
        } else {
          state.deliveryBoard = updatedBoard;
          pruneDeliveryDrafts();
        }
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        renderDeliveryWorkspacePreservingScroll();
      }
    }, null, { preserveScroll: true });
  }

  async function moveDeliveryOrderToTrip(orderId, driverId, tripNo) {
    await runDeliveryAction(`delivery-move:${orderId}:${tripNo}`, async (context) => {
      const updatedBoard = await api.assignDeliveryWorkspaceOrder({
        ...dispatchMetadataForContext(context),
        order_id: orderId,
        driver_id: driverId,
        trip_no: tripNo,
      });
      if (isDeliveryMutationCurrent(context)) {
        if (context.route === "delivery/trip-summary") {
          state.deliveryTripSummaryBoard = updatedBoard;
          pruneDeliveryVehicleDrafts(updatedBoard);
        } else {
          state.deliveryBoard = updatedBoard;
          pruneDeliveryDrafts();
        }
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        renderDeliveryWorkspacePreservingScroll();
      }
    }, null, { preserveScroll: true });
  }

  async function unassignDeliveryOrder(orderId) {
    await runDeliveryAction(`delivery-unassign:${orderId}`, async (context) => {
      const updatedBoard = await api.unassignDeliveryWorkspaceOrder({
        ...dispatchMetadataForContext(context),
        order_id: orderId,
      });
      if (isDeliveryMutationCurrent(context)) {
        if (context.route === "delivery/trip-summary") {
          state.deliveryTripSummaryBoard = updatedBoard;
          pruneDeliveryVehicleDrafts(updatedBoard);
        } else {
          state.deliveryBoard = updatedBoard;
          pruneDeliveryDrafts();
        }
        const { [orderId]: _removed, ...remaining } = state.deliveryAssignmentDrafts;
        state.deliveryAssignmentDrafts = remaining;
        renderDeliveryWorkspacePreservingScroll();
      }
    }, null, { preserveScroll: true });
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
    return (currentDeliveryBoard()?.assignments || []).find(
      (assignment) => assignment.task_id === orderId,
    );
  }

  function findDeliveryOrder(orderId) {
    return (currentDeliveryBoard()?.orders || []).find(
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
    pruneDeliveryVehicleDrafts(state.deliveryBoard);
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

  function defaultDeliveryOrderForm(order = {}) {
    return {
      invoice_number: order.invoice_number || "",
      invoice_date: order.invoice_date || "",
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
      carton_quantity: String(order.carton_quantity ?? 0),
      note: order.note || "",
      product_lines: (order.product_lines || []).map((line) => ({
        _draft_id: nextDeliveryProductLineDraftId(),
        product_code: line.product_code || "",
        product_name: line.product_name || "",
        quantity: Number(line.quantity || 0),
        unit: line.unit || "KG",
        package_quantity: line.package_quantity ?? "",
        package_unit: line.package_unit || "",
      })),
    };
  }

  function deliveryOrderFormFromOrder(order) {
    return defaultDeliveryOrderForm(order);
  }

  function deliveryOrderPayload(form) {
    return {
      invoice_number: form.invoice_number || null,
      invoice_date: form.invoice_date || null,
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
      carton_quantity: Number(form.carton_quantity || 0),
      note: form.note || null,
      product_lines: (form.product_lines || []).map((line) => ({
        product_code: line.product_code || null,
        product_name: line.product_name || "",
        quantity: Number(line.quantity || 0),
        unit: line.unit || "KG",
        package_quantity: line.package_quantity === ""
          || line.package_quantity === null
          || line.package_quantity === undefined
          ? null
          : Number(line.package_quantity),
        package_unit: line.package_unit || null,
      })),
    };
  }

  return {
    updateDeliveryTaskPoolFilter,
    clearDeliveryTaskPoolFilters,
    openDeliveryOrderDetail,
    closeDeliveryOrderModal,
    openAddDeliveryOrder,
    startEditDeliveryOrder,
    cancelDeliveryOrderEdit,
    updateDeliveryOrderForm,
    addDeliveryOrderProductLine,
    updateDeliveryOrderProductLine,
    removeDeliveryOrderProductLine,
    saveDeliveryOrderForm,
    cancelActiveDeliveryOrder,
    updateDeliveryAssignmentDraft,
    applyDeliveryOrderAssignment,
    moveDeliveryOrderToTrip,
    unassignDeliveryOrder,
    getDeliveryAssignmentDraft,
    findDeliveryAssignment,
    findDeliveryOrder,
    pruneDeliveryDrafts,
    clearDeliveryTaskPoolModals,
    focusDeliveryOrderDetailTrigger,
    defaultDeliveryOrderForm,
    deliveryOrderFormFromOrder,
    deliveryOrderPayload,
  };
}
