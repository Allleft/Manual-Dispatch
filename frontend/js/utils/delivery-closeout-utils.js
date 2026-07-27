export const DELIVERY_RETURN_REASONS = [
  ["TIME_RAN_OUT", "Time ran out"],
  ["CUSTOMER_UNAVAILABLE", "Customer unavailable"],
  ["CUSTOMER_CLOSED", "Customer closed"],
  ["INCORRECT_ADDRESS", "Incorrect address"],
  ["DELIVERY_REFUSED", "Delivery refused"],
  ["DRIVER_OR_VEHICLE_ISSUE", "Driver or vehicle issue"],
  ["LOAD_OR_STOCK_ISSUE", "Load or stock issue"],
  ["OTHER", "Other"],
];

export function createDeliveryCloseoutDraft(runSheet) {
  return {
    run_sheet_id: runSheet.run_sheet_id,
    delivery_date: runSheet.delivery_date,
    driver_name: runSheet.driver_name_snapshot || runSheet.driver_id,
    error: "",
    rows: (runSheet.trips || []).flatMap((trip) =>
      (trip.orders || []).map((order) => ({
        run_sheet_row_id: order.row_id,
        outcome: "",
        reason_code: "",
        note: "",
        next_delivery_date: "",
        row_no: order.row_no,
        trip_no: order.trip_no || trip.trip_no,
        order_label:
          order.invoice_number_snapshot
          || order.order_no_snapshot
          || order.order_id_snapshot
          || order.task_id,
        company_name: order.company_name_snapshot || "",
        delivery_address: order.delivery_address_snapshot || "",
        suburb: order.suburb_snapshot || "",
      }))),
  };
}

export function validateDeliveryCloseoutDraft(draft) {
  if (!draft?.rows?.length) {
    return "This Delivery Run Sheet has no orders to close.";
  }
  for (const row of draft.rows) {
    if (!["DELIVERED", "RETURN_TO_POOL"].includes(row.outcome)) {
      return `Choose an outcome for ${row.order_label}.`;
    }
    if (row.outcome !== "RETURN_TO_POOL") {
      continue;
    }
    if (!DELIVERY_RETURN_REASONS.some(([code]) => code === row.reason_code)) {
      return `Choose a return reason for ${row.order_label}.`;
    }
    if (!row.next_delivery_date) {
      return `Choose the next delivery date for ${row.order_label}.`;
    }
    if (row.next_delivery_date <= draft.delivery_date) {
      return `The next delivery date for ${row.order_label} must be later than ${draft.delivery_date}.`;
    }
    if (row.reason_code === "OTHER" && !String(row.note || "").trim()) {
      return `Add a note for the Other reason on ${row.order_label}.`;
    }
  }
  return "";
}

export function buildDeliveryCloseoutPayload(draft) {
  return {
    rows: (draft.rows || []).map((row) => ({
      run_sheet_row_id: row.run_sheet_row_id,
      outcome: row.outcome,
      reason_code: row.outcome === "RETURN_TO_POOL" ? row.reason_code : null,
      note: (
        row.outcome === "RETURN_TO_POOL" && String(row.note || "").trim()
      ) || null,
      next_delivery_date:
        row.outcome === "RETURN_TO_POOL" ? row.next_delivery_date : null,
    })),
  };
}

export function buildDeliveryCloseoutConfirmation(draft) {
  const delivered = draft.rows.filter((row) => row.outcome === "DELIVERED");
  const returned = draft.rows.filter((row) => row.outcome === "RETURN_TO_POOL");
  const returnedLines = returned.map((row) =>
    `- ${row.order_label} (${row.company_name || "Unknown customer"}) → ${row.next_delivery_date} / ${row.reason_code}`);
  return [
    `Close ${draft.run_sheet_id}?`,
    `${delivered.length} delivered; ${returned.length} returned to the Delivery Task Pool.`,
    returnedLines.length ? `Returned orders:\n${returnedLines.join("\n")}` : "",
    "Closing the run sheet cannot be edited through this workflow. Delivered orders will be finalized. Undelivered orders will be unassigned and returned to the Delivery Task Pool.",
  ].filter(Boolean).join("\n\n");
}
