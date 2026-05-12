import {
  apiCancelOrder,
  apiCreateOrder,
  apiUpdateOrder,
} from "../api/manual-dispatch-api.js";
import { DEFAULT_DISPATCH_DATE } from "../state/app-state.js";
import {
  getDisplayPalletQuantity,
  getLooseBagsQuantity,
  getUrgencyLabel,
} from "../utils/format-utils.js";

export function createOrderActions({
  clearError,
  loadBoard,
  renderAddOrderPopup,
  renderBoard,
  renderOrderDetailPopup,
  showError,
  state,
}) {
  function getDefaultAddOrderForm() {
    return {
      invoice_number: "",
      company_name: "",
      phone: "",
      delivery_address: "",
      suburb: "",
      postcode: "",
      delivery_date: state.dispatchDate || DEFAULT_DISPATCH_DATE,
      zone: "",
      urgency: "Normal",
      preferred_driver_id: "",
      pallet_quantity: "0",
      loose_bags_quantity: "0",
      start_time: "",
      end_time: "",
      note: "",
    };
  }

  function openAddOrder() {
    state.isAddOrderOpen = true;
    state.addOrderError = "";
    state.addOrderForm = getDefaultAddOrderForm();
    renderAddOrderPopup();
  }

  function closeAddOrder() {
    state.isAddOrderOpen = false;
    state.addOrderError = "";
    state.addOrderForm = {};
    renderAddOrderPopup();
  }

  function updateAddOrderForm(field, value) {
    state.addOrderForm = {
      ...state.addOrderForm,
      [field]: value,
    };
  }

  function getAddOrderPayload() {
    return {
      ...state.addOrderForm,
      pallet_quantity: Number(state.addOrderForm.pallet_quantity || 0),
      loose_bags_quantity: Number(state.addOrderForm.loose_bags_quantity || 0),
    };
  }

  function getOrderEditForm(order) {
    return {
      invoice_number: order.invoice_number || "",
      company_name: order.company_name || "",
      phone: order.phone || "",
      delivery_address: order.delivery_address || "",
      suburb: order.suburb || "",
      postcode: order.postcode || "",
      delivery_date: order.delivery_date || "",
      zone: order.zone || "",
      urgency: getUrgencyLabel(order),
      preferred_driver_id: order.preferred_driver_id || "",
      pallet_quantity: String(getDisplayPalletQuantity(order)),
      loose_bags_quantity: String(getLooseBagsQuantity(order)),
      start_time: order.start_time || "",
      end_time: order.end_time || "",
      note: order.note || "",
    };
  }

  function startOrderEdit(order) {
    state.isOrderEditMode = true;
    state.orderEditError = "";
    state.orderEditForm = getOrderEditForm(order);
    renderOrderDetailPopup();
  }

  function cancelOrderEdit() {
    state.isOrderEditMode = false;
    state.orderEditError = "";
    state.orderEditForm = {};
    renderOrderDetailPopup();
  }

  function updateOrderEditForm(field, value) {
    state.orderEditForm = {
      ...state.orderEditForm,
      [field]: value,
    };
  }

  function getOrderEditPayload() {
    return {
      ...state.orderEditForm,
      pallet_quantity: Number(state.orderEditForm.pallet_quantity || 0),
      loose_bags_quantity: Number(state.orderEditForm.loose_bags_quantity || 0),
    };
  }

  function openOrderDetail(orderId) {
    state.activeOrderDetailId = orderId;
    state.isOrderEditMode = false;
    state.orderEditError = "";
    state.orderEditForm = {};
    renderOrderDetailPopup();
  }

  function closeOrderDetail() {
    state.activeOrderDetailId = "";
    state.isOrderEditMode = false;
    state.orderEditError = "";
    state.orderEditForm = {};
    renderOrderDetailPopup();
  }

  async function handleCreateOrder() {
    if (state.isSaving) {
      return;
    }

    state.isSaving = true;
    state.addOrderError = "";
    renderAddOrderPopup();

    try {
      await apiCreateOrder(getAddOrderPayload());
      closeAddOrder();
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      state.addOrderError = `Unable to save Order. ${error.message}`;
      renderAddOrderPopup();
    }
  }

  async function handleUpdateOrder(orderId) {
    if (state.isSaving) {
      return;
    }

    state.isSaving = true;
    state.orderEditError = "";
    renderOrderDetailPopup();

    try {
      await apiUpdateOrder(orderId, getOrderEditPayload());
      state.isOrderEditMode = false;
      state.orderEditError = "";
      state.orderEditForm = {};
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      state.orderEditError = `Unable to save changes. ${error.message}`;
      renderOrderDetailPopup();
    }
  }

  async function handleCancelOrder(orderId) {
    if (state.isSaving) {
      return;
    }

    const confirmed = window.confirm(
      "Cancel this Order? Cancelled Orders are hidden from the Task Pool and excluded from export.",
    );
    if (!confirmed) {
      return;
    }

    state.isSaving = true;
    clearError();
    renderOrderDetailPopup();

    try {
      await apiCancelOrder(orderId);
      closeOrderDetail();
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      showError(`Unable to cancel Order. ${error.message}`);
      renderBoard();
    }
  }

  return {
    cancelOrderEdit,
    closeAddOrder,
    closeOrderDetail,
    getOrderEditForm,
    handleCancelOrder,
    handleCreateOrder,
    handleUpdateOrder,
    openAddOrder,
    openOrderDetail,
    startOrderEdit,
    updateAddOrderForm,
    updateOrderEditForm,
  };
}
