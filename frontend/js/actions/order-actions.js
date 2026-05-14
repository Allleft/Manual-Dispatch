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
      product_lines: [],
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
    const nextForm = {
      ...state.addOrderForm,
      [field]: value,
    };
    if (field === "pallet_quantity" && Number(value || 0) > 0) {
      nextForm.loose_bags_quantity = "0";
    }
    if (field === "loose_bags_quantity" && Number(value || 0) > 0) {
      nextForm.pallet_quantity = "0";
    }
    state.addOrderForm = {
      ...nextForm,
    };
  }

  function getAddOrderPayload() {
    return {
      ...state.addOrderForm,
      pallet_quantity: Number(state.addOrderForm.pallet_quantity || 0),
      loose_bags_quantity: Number(state.addOrderForm.loose_bags_quantity || 0),
      product_lines: normalizeProductLinePayload(state.addOrderForm.product_lines),
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
      product_lines: (order.product_lines || []).map((line) => ({
        product_name: line.product_name || "",
        quantity: String(line.quantity || ""),
        unit: line.unit || "PALLETS",
      })),
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
    const nextForm = {
      ...state.orderEditForm,
      [field]: value,
    };
    if (field === "pallet_quantity" && Number(value || 0) > 0) {
      nextForm.loose_bags_quantity = "0";
    }
    if (field === "loose_bags_quantity" && Number(value || 0) > 0) {
      nextForm.pallet_quantity = "0";
    }
    state.orderEditForm = {
      ...nextForm,
    };
  }

  function getOrderEditPayload() {
    return {
      ...state.orderEditForm,
      pallet_quantity: Number(state.orderEditForm.pallet_quantity || 0),
      loose_bags_quantity: Number(state.orderEditForm.loose_bags_quantity || 0),
      product_lines: normalizeProductLinePayload(state.orderEditForm.product_lines),
    };
  }

  function openOrderDetail(orderId) {
    state.activeOrderDetailId = orderId;
    state.isProductDetailOpen = false;
    state.isOrderEditMode = false;
    state.orderEditError = "";
    state.orderEditForm = {};
    renderOrderDetailPopup();
  }

  function closeOrderDetail() {
    state.activeOrderDetailId = "";
    state.isProductDetailOpen = false;
    state.isOrderEditMode = false;
    state.orderEditError = "";
    state.orderEditForm = {};
    renderOrderDetailPopup();
  }

  async function handleCreateOrder() {
    if (state.isSaving) {
      return;
    }

    const loadError = getLoadExclusivityError(state.addOrderForm);
    if (loadError) {
      state.addOrderError = loadError;
      renderAddOrderPopup();
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

    const loadError = getLoadExclusivityError(state.orderEditForm);
    if (loadError) {
      state.orderEditError = loadError;
      renderOrderDetailPopup();
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

  function toggleProductDetail() {
    state.isProductDetailOpen = !state.isProductDetailOpen;
    renderOrderDetailPopup();
  }

  function addProductLine(formKey) {
    const form = formKey === "edit" ? state.orderEditForm : state.addOrderForm;
    const nextLines = [...(form.product_lines || []), createEmptyProductLine(form)];
    updateProductLines(formKey, nextLines, { rerenderPopup: true });
  }

  function removeProductLine(formKey, index) {
    const form = formKey === "edit" ? state.orderEditForm : state.addOrderForm;
    const nextLines = (form.product_lines || []).filter((_, lineIndex) => lineIndex !== index);
    updateProductLines(formKey, nextLines, { rerenderPopup: true });
  }

  function updateProductLine(formKey, index, field, value) {
    const form = formKey === "edit" ? state.orderEditForm : state.addOrderForm;
    const nextLines = (form.product_lines || []).map((line, lineIndex) =>
      lineIndex === index ? { ...line, [field]: value } : line,
    );
    updateProductLines(formKey, nextLines, { rerenderPopup: false });
  }

  function updateProductLines(formKey, productLines, { rerenderPopup = true } = {}) {
    if (formKey === "edit") {
      state.orderEditForm = {
        ...state.orderEditForm,
        product_lines: productLines,
      };
      if (rerenderPopup) {
        renderOrderDetailPopup();
      }
      return;
    }

    state.addOrderForm = {
      ...state.addOrderForm,
      product_lines: productLines,
    };
    if (rerenderPopup) {
      renderAddOrderPopup();
    }
  }

  function createEmptyProductLine(form) {
    return {
      product_name: "",
      quantity: "1",
      unit: getPreferredProductUnit(form),
    };
  }

  function getPreferredProductUnit(form) {
    if (Number(form.loose_bags_quantity || 0) > 0) {
      return "BAGS";
    }
    return "PALLETS";
  }

  function normalizeProductLinePayload(productLines) {
    return (productLines || []).map((line) => ({
      product_name: line.product_name || "",
      quantity: Number(line.quantity || 0),
      unit: line.unit || "",
    }));
  }

  function getLoadExclusivityError(form) {
    const pallets = Number(form.pallet_quantity || 0);
    const looseBags = Number(form.loose_bags_quantity || 0);
    return pallets > 0 && looseBags > 0
      ? "Order must use either Pallets or Bags, not both."
      : "";
  }

  return {
    cancelOrderEdit,
    closeAddOrder,
    closeOrderDetail,
    getOrderEditForm,
    handleCancelOrder,
    handleCreateOrder,
    handleUpdateOrder,
    addProductLine,
    openAddOrder,
    openOrderDetail,
    removeProductLine,
    startOrderEdit,
    toggleProductDetail,
    updateAddOrderForm,
    updateProductLine,
    updateOrderEditForm,
  };
}
