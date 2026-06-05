import {
  apiCreateGeneratedFinalSummary,
  apiExportFinalSummariesExcel,
  apiListFinalSummaries,
  apiSaveGeneratedFinalSummary,
  apiSaveFinalSummary,
  apiUnassignTask,
  formatApiErrorDetail,
} from "../api/manual-dispatch-api.js";
import {
  findDriverById,
  getAssignedOpShopPickupsForDriver,
  getAssignedOrdersForDriver,
  getAssignmentsForDriver,
  getFinalSummaryKey,
  getOrderByTaskId,
  getSelectedVehicleForDriver,
  getTaskKey,
} from "../state/selectors.js";
import {
  getDisplayPalletQuantity,
  getLooseBagsQuantity,
} from "../utils/format-utils.js";
import { downloadExcelResponse } from "../utils/download-utils.js";

function normalizeSuburbName(suburb) {
  return String(suburb || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLocaleLowerCase();
}

function normalizeStartTime(startTime) {
  const text = String(startTime || "").trim();
  if (!text) {
    return "";
  }
  const parts = text.split(":");
  if (parts.length < 2) {
    return text;
  }
  return `${String(parts[0]).padStart(2, "0")}:${String(parts[1]).padStart(2, "0")}`;
}

function sortFinalSummaryOrders(orders) {
  return [...orders].sort((first, second) => {
    const firstDistance = first.estimated_distance_km_from_warehouse_snapshot ??
      first.estimated_distance_km_from_warehouse;
    const secondDistance = second.estimated_distance_km_from_warehouse_snapshot ??
      second.estimated_distance_km_from_warehouse;
    const firstKnown = firstDistance !== null && firstDistance !== undefined && firstDistance !== "";
    const secondKnown = secondDistance !== null && secondDistance !== undefined && secondDistance !== "";
    if (firstKnown !== secondKnown) {
      return firstKnown ? -1 : 1;
    }
    if (firstKnown && Number(firstDistance) !== Number(secondDistance)) {
      return Number(firstDistance) - Number(secondDistance);
    }

    const suburbCompare = normalizeSuburbName(first.suburb || first.suburb_snapshot)
      .localeCompare(normalizeSuburbName(second.suburb || second.suburb_snapshot));
    if (suburbCompare !== 0) {
      return suburbCompare;
    }

    const firstStart = normalizeStartTime(first.start_time || first.start_time_snapshot);
    const secondStart = normalizeStartTime(second.start_time || second.start_time_snapshot);
    if (Boolean(firstStart) !== Boolean(secondStart)) {
      return firstStart ? -1 : 1;
    }
    if (firstStart && secondStart && firstStart !== secondStart) {
      return firstStart.localeCompare(secondStart);
    }

    const invoiceCompare = String(first.invoice_number || first.invoice_number_snapshot || "")
      .localeCompare(String(second.invoice_number || second.invoice_number_snapshot || ""));
    if (invoiceCompare !== 0) {
      return invoiceCompare;
    }
    return String(first.order_id || first.order_id_snapshot || first.task_id || "")
      .localeCompare(String(second.order_id || second.order_id_snapshot || second.task_id || ""));
  });
}

export function createFinalSummaryActions({
  clearError,
  loadBoard,
  loadFinalSummaryDates,
  renderBoard,
  renderFinalTripSummaries,
  showError,
  state,
}) {
  function normalizeFinalSummary(summary) {
    return {
      summary_id: summary.summary_id || "",
      dispatch_date: summary.dispatch_date || state.dispatchDate,
      delivery_date: summary.delivery_date || state.driverSummaryDeliveryDate || summary.dispatch_date || state.dispatchDate,
      driver_id: summary.driver_id || "",
      driver_name: summary.driver_name || summary.driver_name_snapshot || "",
      driver_name_snapshot: summary.driver_name_snapshot || summary.driver_name || "",
      vehicle_id: summary.vehicle_id || "",
      vehicle_rego: summary.vehicle_rego || summary.vehicle_rego_snapshot || "No vehicle selected",
      vehicle_rego_snapshot: summary.vehicle_rego_snapshot || summary.vehicle_rego || "No vehicle selected",
      total_pallets: Number(summary.total_pallets || 0),
      total_loose_bags: Number(summary.total_loose_bags || 0),
      status: summary.status || (summary.summary_id ? "SAVED" : "LOCKED"),
      generated_at: summary.generated_at || "",
      saved_at: summary.saved_at || "",
      saved_by_account_name:
        summary.saved_by_account_name ||
        (summary.summary_id ? "Unknown" : state.accountName || "Unknown"),
      saved_by_account_id: summary.saved_by_account_id || "",
      trips: (summary.trips || [])
        .map((trip) => ({
          trip_no: trip.trip_no,
          orders: (trip.orders || []).map((order) => ({
            row_id: order.row_id || "",
            row_no: Number(order.row_no || 0),
            task_type: order.task_type || "ORDER",
            task_id: order.task_id || order.order_id || order.order_id_snapshot || "",
            order_id: order.order_id || order.order_id_snapshot || order.task_id || "",
            invoice_number: order.invoice_number || order.invoice_number_snapshot || "",
            company_name: order.company_name || order.company_name_snapshot || "",
            suburb: order.suburb || order.suburb_snapshot || "",
            delivery_address: order.delivery_address || order.delivery_address_snapshot || "",
            product: order.product || order.product_snapshot || "",
            estimated_distance_km_from_warehouse:
              order.estimated_distance_km_from_warehouse ??
              order.estimated_distance_km_from_warehouse_snapshot ??
              null,
            estimated_distance_km_from_warehouse_snapshot:
              order.estimated_distance_km_from_warehouse_snapshot ??
              order.estimated_distance_km_from_warehouse ??
              null,
            product_lines_snapshot:
              order.product_lines_snapshot ||
              order.product_lines ||
              [],
            pallet_quantity: Number(
              order.pallet_quantity ?? order.pallet_quantity_snapshot ?? 0,
            ),
            loose_bags_quantity: Number(
              order.loose_bags_quantity ?? order.loose_bags_quantity_snapshot ?? 0,
            ),
            note: order.note || order.note_snapshot || "",
            start_time: order.start_time || order.start_time_snapshot || "",
          })),
        }))
        .filter((trip) => trip.orders.length > 0),
      opshop_pickups: (summary.opshop_pickups || []).map((pickup, index) => ({
        row_id: pickup.row_id || "",
        row_no: Number(pickup.row_no || index + 1),
        task_type: "OPSHOP_PICKUP",
        pickup_task_id: pickup.pickup_task_id || pickup.pickup_task_id_snapshot || "",
        opshop_name: pickup.opshop_name || pickup.opshop_name_snapshot || "",
        suburb: pickup.suburb || pickup.suburb_snapshot || "",
        street_address: pickup.street_address || pickup.street_address_snapshot || "",
        area_region: pickup.area_region || pickup.area_region_snapshot || "",
        pickup_date: pickup.pickup_date || pickup.pickup_date_snapshot || "",
        run_type: pickup.run_type || pickup.run_type_snapshot || "",
        pickup_category: pickup.pickup_category || pickup.pickup_category_snapshot || "",
        route_group_id: pickup.route_group_id || pickup.route_group_id_snapshot || "",
        route_group_name: pickup.route_group_name || pickup.route_group_name_snapshot || "",
        pickup_frequency: pickup.pickup_frequency || pickup.pickup_frequency_snapshot || "",
        time_window: pickup.time_window || pickup.time_window_snapshot || "",
        primary_contact: pickup.primary_contact || pickup.primary_contact_snapshot || "",
        primary_phone: pickup.primary_phone || pickup.primary_phone_snapshot || "",
        secondary_contact: pickup.secondary_contact || pickup.secondary_contact_snapshot || "",
        secondary_phone: pickup.secondary_phone || pickup.secondary_phone_snapshot || "",
        access_type: pickup.access_type || pickup.access_type_snapshot || "",
        key_required: Boolean(
          pickup.key_required ?? pickup.key_required_snapshot ?? false,
        ),
        trailer_restriction: pickup.trailer_restriction || pickup.trailer_restriction_snapshot || "",
        notes: pickup.notes || pickup.notes_snapshot || "",
        status: pickup.status || pickup.status_snapshot || "",
      })),
    };
  }

  function addGeneratedTaskKeys(summary) {
    const normalized = normalizeFinalSummary(summary);
    normalized.trips.forEach((trip) => {
      trip.orders.forEach((order) => {
        state.generatedTaskKeys.add(getTaskKey(order.task_type, order.task_id));
      });
    });
    normalized.opshop_pickups.forEach((pickup) => {
      state.generatedTaskKeys.add(getTaskKey("OPSHOP_PICKUP", pickup.pickup_task_id));
    });
  }

  async function exportFinalSummariesExcel(dispatchDate, deliveryDate) {
    const response = await apiExportFinalSummariesExcel(dispatchDate, deliveryDate);
    if (!response.ok) {
      let message = `Export failed with status ${response.status}`;
      try {
        const payload = await response.json();
        message = formatApiErrorDetail(payload.detail) || message;
      } catch (error) {
        message = response.statusText || message;
      }
      throw new Error(message);
    }

    await downloadExcelResponse(response, `final-trip-summary-${dispatchDate}.xlsx`);
  }

  function buildFinalTripSummarySnapshot(driverId) {
    if (!state.driverSummaryDeliveryDate) {
      throw new Error("Please select a Delivery Date before generating Final Trip Summary.");
    }

    const driver = findDriverById(driverId);
    if (!driver) {
      throw new Error(`Driver does not exist: ${driverId}`);
    }

    const selectedVehicle = getSelectedVehicleForDriver(driverId);
    const assignments = getAssignmentsForDriver(driverId);
    const trips = ["trip1", "trip2"]
      .map((tripNo) => {
        const tripOrders = assignments
          .filter((assignment) => assignment.trip_no === tripNo)
          .map((assignment) => {
            const order = getOrderByTaskId(assignment.task_id);
            if (!order) {
              return null;
            }
            return {
              task_type: assignment.task_type,
              task_id: assignment.task_id,
              order_id: order.order_id,
              order_id_snapshot: order.order_id,
              invoice_number_snapshot: order.invoice_number || "",
              company_name_snapshot: order.company_name || "",
              suburb_snapshot: order.suburb || "",
              delivery_address_snapshot: order.delivery_address || "",
              product_snapshot: "",
              product_lines_snapshot: (order.product_lines || []).map((line) => ({
                product_name: line.product_name || "",
                quantity: Number(line.quantity || 0),
                unit: line.unit || "",
              })),
              pallet_quantity_snapshot: getDisplayPalletQuantity(order),
              loose_bags_quantity_snapshot: getLooseBagsQuantity(order),
              note_snapshot: order.note || "",
              estimated_distance_km_from_warehouse_snapshot:
                order.estimated_distance_km_from_warehouse ?? null,
              estimated_distance_km_from_warehouse:
                order.estimated_distance_km_from_warehouse ?? null,
              company_name: order.company_name || "",
              suburb: order.suburb || "",
              invoice_number: order.invoice_number || "",
              delivery_address: order.delivery_address || "",
              start_time: order.start_time || "",
              pallet_quantity: getDisplayPalletQuantity(order),
              loose_bags_quantity: getLooseBagsQuantity(order),
              note: order.note || "",
              product: "",
              product_lines: (order.product_lines || []).map((line) => ({
                product_name: line.product_name || "",
                quantity: Number(line.quantity || 0),
                unit: line.unit || "",
              })),
            };
          })
          .filter(Boolean);

        return {
          trip_no: tripNo,
          orders: sortFinalSummaryOrders(tripOrders),
        };
      })
      .filter((trip) => trip.orders.length > 0);

    const allOrders = trips.flatMap((trip) => trip.orders);
    const opshopPickups = getAssignedOpShopPickupsForDriver(driverId).map((pickup, index) => ({
      row_no: index + 1,
      task_type: "OPSHOP_PICKUP",
      pickup_task_id: pickup.pickup_task_id,
      opshop_name: pickup.opshop_name || "",
      suburb: pickup.suburb || "",
      street_address: pickup.street_address || "",
      area_region: pickup.area_region || "",
      pickup_date: pickup.pickup_date || "",
      run_type: pickup.run_type || "",
      pickup_category: pickup.pickup_category || "",
      route_group_id: pickup.route_group_id || "",
      route_group_name: pickup.route_group_name || "",
      pickup_frequency: pickup.pickup_frequency || "",
      time_window: pickup.time_window || "",
      primary_contact: pickup.primary_contact || "",
      primary_phone: pickup.primary_phone || "",
      secondary_contact: pickup.secondary_contact || "",
      secondary_phone: pickup.secondary_phone || "",
      access_type: pickup.access_type || "",
      key_required: Boolean(pickup.key_required),
      trailer_restriction: pickup.trailer_restriction || "",
      notes: [pickup.status_notes, pickup.task_notes].filter(Boolean).join("\n"),
      status: pickup.status || "",
    }));

    return {
      generated_at: new Date().toISOString(),
      dispatch_date: state.dispatchDate,
      delivery_date: state.driverSummaryDeliveryDate,
      driver_id: driver.driver_id,
      driver_name: driver.name,
      driver_name_snapshot: driver.name,
      vehicle_id: selectedVehicle ? selectedVehicle.vehicle_id : "",
      vehicle_rego: selectedVehicle ? selectedVehicle.rego : "No vehicle selected",
      vehicle_rego_snapshot: selectedVehicle ? selectedVehicle.rego : "No vehicle selected",
      total_pallets: allOrders.reduce((total, order) => total + Number(order.pallet_quantity || 0), 0),
      total_loose_bags: allOrders.reduce((total, order) => total + Number(order.loose_bags_quantity || 0), 0),
      saved_by_account_name: state.accountName || "",
      saved_by_account_id: state.accountId || "",
      status: "GENERATED",
      trips,
      opshop_pickups: opshopPickups,
    };
  }

  async function handleGenerateDriverSummary(driverId) {
    if (state.isSaving || state.isLoading) {
      return;
    }

    if (!state.driverSummaryDeliveryDate) {
      showError("Please select a Delivery Date before generating Final Trip Summary.");
      renderBoard();
      return;
    }

    const summaryKey = getFinalSummaryKey(driverId);
    if (state.finalTripSummaries[summaryKey]) {
      showError("Final Trip Summary for this driver is already generated and locked.");
      renderBoard();
      return;
    }

    const assignedOrders = getAssignedOrdersForDriver(driverId);
    const assignedOpShopPickups = getAssignedOpShopPickupsForDriver(driverId);
    if (assignedOrders.length === 0 && assignedOpShopPickups.length === 0) {
      showError("Assign at least one Order or OP SHOP pickup before generating a Final Trip Summary.");
      renderBoard();
      return;
    }

    let snapshot;
    try {
      snapshot = buildFinalTripSummarySnapshot(driverId);
    } catch (error) {
      showError(`Unable to generate Final Trip Summary. ${error.message}`);
      renderBoard();
      return;
    }

    state.finalSummaryGlobalSaveError = "";
    state.finalSummaryGlobalSaveSuccess = "";
    state.isSaving = true;
    clearError();
    renderBoard();

    try {
      const generatedSummary = normalizeFinalSummary(
        await apiCreateGeneratedFinalSummary(getFinalSummarySavePayload(snapshot)),
      );
      state.finalTripSummaries[
        getFinalSummaryKey(generatedSummary.driver_id, generatedSummary.delivery_date)
      ] = generatedSummary;
      addGeneratedTaskKeys(generatedSummary);

      const generatedOrderTasks = generatedSummary.trips.flatMap((trip) => trip.orders);
      await Promise.all(
        generatedOrderTasks.map((order) =>
          apiUnassignTask({
            dispatch_date: state.dispatchDate,
            task_type: order.task_type,
            task_id: order.task_id,
          }),
        ),
      );
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      showError(`Unable to generate Final Trip Summary. ${error.message}`);
      renderBoard();
    }
  }

  function getFinalSummarySavePayload(summary) {
    const normalized = normalizeFinalSummary(summary);
    return {
      dispatch_date: normalized.dispatch_date,
      delivery_date: normalized.delivery_date,
      driver_id: normalized.driver_id,
      driver_name_snapshot: normalized.driver_name_snapshot || normalized.driver_name,
      vehicle_id: normalized.vehicle_id || null,
      vehicle_rego_snapshot: normalized.vehicle_rego_snapshot || "No vehicle selected",
      total_pallets: normalized.total_pallets,
      total_loose_bags: normalized.total_loose_bags,
      generated_at: normalized.generated_at,
      saved_by_account_name: state.accountName || normalized.saved_by_account_name,
      saved_by_account_id: state.accountId || normalized.saved_by_account_id || null,
      trips: normalized.trips.map((trip) => ({
        trip_no: trip.trip_no,
        orders: trip.orders.map((order) => ({
          task_type: order.task_type,
          task_id: order.task_id,
          order_id_snapshot: order.order_id,
          invoice_number_snapshot: order.invoice_number,
          company_name_snapshot: order.company_name,
          suburb_snapshot: order.suburb,
          delivery_address_snapshot: order.delivery_address,
          product_snapshot: order.product,
          product_lines_snapshot: order.product_lines_snapshot || order.product_lines || [],
          estimated_distance_km_from_warehouse_snapshot:
            order.estimated_distance_km_from_warehouse_snapshot ??
            order.estimated_distance_km_from_warehouse ??
            null,
          start_time: order.start_time || "",
          pallet_quantity_snapshot: order.pallet_quantity,
          loose_bags_quantity_snapshot: order.loose_bags_quantity,
          note_snapshot: order.note,
        })),
      })),
      opshop_pickups: normalized.opshop_pickups.map((pickup) => ({
        task_type: "OPSHOP_PICKUP",
        pickup_task_id_snapshot: pickup.pickup_task_id,
        opshop_name_snapshot: pickup.opshop_name,
        suburb_snapshot: pickup.suburb,
        street_address_snapshot: pickup.street_address,
        area_region_snapshot: pickup.area_region,
        pickup_date_snapshot: pickup.pickup_date,
        run_type_snapshot: pickup.run_type,
        pickup_category_snapshot: pickup.pickup_category,
        route_group_id_snapshot: pickup.route_group_id,
        route_group_name_snapshot: pickup.route_group_name,
        pickup_frequency_snapshot: pickup.pickup_frequency,
        time_window_snapshot: pickup.time_window,
        primary_contact_snapshot: pickup.primary_contact,
        primary_phone_snapshot: pickup.primary_phone,
        secondary_contact_snapshot: pickup.secondary_contact,
        secondary_phone_snapshot: pickup.secondary_phone,
        access_type_snapshot: pickup.access_type,
        key_required_snapshot: pickup.key_required,
        trailer_restriction_snapshot: pickup.trailer_restriction,
        notes_snapshot: pickup.notes,
        status_snapshot: pickup.status,
      })),
    };
  }

  function getUnsavedFinalSummaries() {
    return Object.values(state.finalTripSummaries)
      .map(normalizeFinalSummary)
      .filter((summary) =>
        summary.dispatch_date === state.dispatchDate &&
        summary.delivery_date === state.driverSummaryDeliveryDate,
      )
      .filter((summary) => !summary.summary_id || summary.status === "GENERATED");
  }

  async function ensureNoDuplicateFinalSummaries(summaries) {
    const summariesByDate = new Map();
    summaries.forEach((summary) => {
      const existing = summariesByDate.get(summary.dispatch_date) || [];
      existing.push(summary);
      summariesByDate.set(summary.dispatch_date, existing);
    });

    for (const [dispatchDate, dateSummaries] of summariesByDate.entries()) {
      const savedSummaries = await apiListFinalSummaries(dispatchDate);
      const savedKeys = new Set(
        (savedSummaries || []).map((summary) =>
          getFinalSummaryKey(summary.driver_id, summary.delivery_date || summary.dispatch_date),
        ),
      );
      const duplicate = dateSummaries.find((summary) =>
        savedKeys.has(getFinalSummaryKey(summary.driver_id, summary.delivery_date)),
      );
      if (duplicate) {
        throw new Error(
          "Final Summary for this driver, dispatch date, and delivery date has already been saved.",
        );
      }
    }
  }

  async function handleSaveAllFinalSummaries() {
    if (state.isSaving || state.isSavingFinalSummaries || state.isLoading) {
      return;
    }

    const unsavedSummaries = getUnsavedFinalSummaries();
    state.finalSummaryGlobalSaveError = "";
    state.finalSummaryGlobalSaveSuccess = "";

    if (!state.isLoggedIn || !state.accountName) {
      state.finalSummaryGlobalSaveError =
        "Please log in before saving and exporting Final Trip Summary.";
      renderFinalTripSummaries();
      return;
    }

    if (!state.driverSummaryDeliveryDate) {
      state.finalSummaryGlobalSaveError =
        "Please select a Delivery Date before generating Final Trip Summary.";
      renderFinalTripSummaries();
      return;
    }

    if (unsavedSummaries.length === 0) {
      state.finalSummaryGlobalSaveError = "Generate at least one Final Trip Summary before saving and exporting.";
      renderFinalTripSummaries();
      return;
    }

    state.isSavingFinalSummaries = true;
    state.isSaving = true;
    clearError();
    renderBoard();

    try {
      await ensureNoDuplicateFinalSummaries(unsavedSummaries);

      const savedSummaries = [];
      for (const summary of unsavedSummaries) {
        const savedSummary = normalizeFinalSummary(
          summary.summary_id && summary.status === "GENERATED"
            ? await apiSaveGeneratedFinalSummary(summary.summary_id, {
                saved_by_account_name: state.accountName || summary.saved_by_account_name,
                saved_by_account_id: state.accountId || summary.saved_by_account_id || null,
              })
            : await apiSaveFinalSummary(getFinalSummarySavePayload(summary)),
        );
        state.finalTripSummaries[getFinalSummaryKey(savedSummary.driver_id, savedSummary.delivery_date)] = savedSummary;
        savedSummaries.push(savedSummary);
      }

      await exportFinalSummariesExcel(state.dispatchDate, state.driverSummaryDeliveryDate);

      state.finalSummaryGlobalSaveSuccess = `Final Trip Summary saved and exported by ${state.accountName}.`;
      state.historyLoaded = false;
      await loadFinalSummaryDates({ render: false });
      state.isSavingFinalSummaries = false;
      await loadBoard(state.dispatchDate);
    } catch (error) {
      state.isSaving = false;
      state.isSavingFinalSummaries = false;
      state.finalSummaryGlobalSaveError = `Unable to save and export Final Summary. ${error.message}`;
      renderBoard();
    }
  }

  async function handleLoadFinalSummaryHistory() {
    if (state.isSaving || state.isLoading || state.isHistoryLoading) {
      return;
    }

    state.isHistoryLoading = true;
    state.historyError = "";
    clearError();
    renderBoard();

    try {
      const summaries = await apiListFinalSummaries(state.historyDate || state.dispatchDate);
      state.finalSummaryHistory = (summaries || []).map(normalizeFinalSummary);
      state.historyLoaded = true;
    } catch (error) {
      state.historyError = `Unable to load Final Trip Summary history. ${error.message}`;
    } finally {
      state.isHistoryLoading = false;
      renderBoard();
    }
  }

  return {
    getUnsavedFinalSummaries,
    handleGenerateDriverSummary,
    handleLoadFinalSummaryHistory,
    handleSaveAllFinalSummaries,
    normalizeFinalSummary,
  };
}
