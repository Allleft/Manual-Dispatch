import { formatOptional } from "../../utils/format-utils.js";
import { DELIVERY_RETURN_REASONS } from "../../utils/delivery-closeout-utils.js";
import {
  createActionButton,
  createBoundSelect,
  createBoundTextarea,
  createStatus,
  createWorkspaceModal,
  isBusy,
} from "./delivery-renderer-utils.js";

export function createDeliveryCloseoutModal(state, actions) {
  const draft = state.deliveryRunSheetCloseout;
  if (!draft) {
    return null;
  }
  const actionKey = `delivery-closeout:${draft.run_sheet_id}`;
  const isSubmitting = isBusy(state, actionKey);
  const modal = createWorkspaceModal(
    "Close Delivery Run Sheet",
    actions.closeDeliveryRunSheetCloseout,
    {
      eyebrow: "Delivery closeout",
      subtitle:
        "Record every order as delivered or return it to the Delivery Task Pool.",
      iconName: "document",
      width: "confirmation",
      closeDisabled: isSubmitting,
    },
  );
  const body = modal.querySelector(".workspace-modal-body");
  body.classList.add("workspace-delivery-closeout-body");

  const summary = document.createElement("p");
  summary.className = "workspace-delivery-closeout-summary";
  summary.textContent = [
    draft.driver_name,
    draft.delivery_date,
    `${draft.rows.length} orders`,
  ].join(" | ");
  body.append(summary);

  const bulkActions = document.createElement("div");
  bulkActions.className = "workspace-action-row";
  bulkActions.append(createActionButton(
    "Mark All Delivered",
    actions.markAllDeliveryCloseoutRowsDelivered,
    { disabled: isSubmitting },
  ));
  body.append(bulkActions);

  const list = document.createElement("div");
  list.className = "workspace-delivery-closeout-list";
  draft.rows.forEach((row) => {
    const card = document.createElement("section");
    card.className = "workspace-delivery-closeout-row";
    const heading = document.createElement("div");
    heading.className = "workspace-delivery-closeout-row-heading";
    const name = document.createElement("strong");
    name.textContent = [
      Number.isFinite(Number(row.row_no)) ? `${row.row_no}.` : "",
      formatOptional(row.order_label),
      "-",
      formatOptional(row.company_name),
    ].filter(Boolean).join(" ");
    const trip = document.createElement("span");
    trip.textContent = row.trip_no === "trip2" ? "Trip 2" : "Trip 1";
    heading.append(name, trip);
    card.append(heading);

    const context = document.createElement("p");
    context.className = "workspace-delivery-closeout-row-context";
    context.textContent = [
      formatOptional(row.delivery_address, ""),
      formatOptional(row.suburb, ""),
      `Driver: ${formatOptional(draft.driver_name)}`,
    ].filter(Boolean).join(" | ");
    card.append(context);

    const fields = document.createElement("div");
    fields.className = "workspace-form-grid workspace-delivery-closeout-fields";
    fields.append(createBoundSelect(
      "Outcome",
      row.outcome,
      [
        { value: "", label: "Choose outcome" },
        { value: "DELIVERED", label: "Delivered" },
        { value: "RETURN_TO_POOL", label: "Return to Delivery Task Pool" },
      ],
      (value) => actions.updateDeliveryCloseoutRow(
        row.run_sheet_row_id,
        "outcome",
        value,
      ),
    ));
    if (row.outcome === "RETURN_TO_POOL") {
      fields.append(
        createBoundSelect(
          "Return reason",
          row.reason_code,
          [
            { value: "", label: "Choose reason" },
            ...DELIVERY_RETURN_REASONS.map(([value, label]) => ({ value, label })),
          ],
          (value) => actions.updateDeliveryCloseoutRow(
            row.run_sheet_row_id,
            "reason_code",
            value,
          ),
        ),
      );
      const dateField = document.createElement("label");
      dateField.className = "workspace-field";
      const dateLabel = document.createElement("span");
      dateLabel.textContent = "Next delivery date";
      const dateInput = document.createElement("input");
      dateInput.type = "date";
      dateInput.min = nextDateAfter(draft.delivery_date);
      dateInput.value = row.next_delivery_date || "";
      dateInput.addEventListener("change", () =>
        actions.updateDeliveryCloseoutRow(
          row.run_sheet_row_id,
          "next_delivery_date",
          dateInput.value,
        ));
      dateField.append(dateLabel, dateInput);
      fields.append(dateField);
      fields.append(createBoundTextarea(
        row.reason_code === "OTHER" ? "Note (required)" : "Note (optional)",
        row.note,
        (value) => actions.updateDeliveryCloseoutRow(
          row.run_sheet_row_id,
          "note",
          value,
        ),
      ));
    }
    card.append(fields);
    list.append(card);
  });
  body.append(list);

  if (draft.error) {
    body.append(createStatus(draft.error, "error"));
  }
  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-delivery-closeout-actions";
  actionsRow.append(
    createActionButton("Cancel", actions.closeDeliveryRunSheetCloseout, {
      disabled: isSubmitting,
    }),
    createActionButton(
      isSubmitting ? "Closing Run Sheet..." : "Review and Close",
      actions.submitDeliveryRunSheetCloseout,
      { disabled: isSubmitting, primary: true },
    ),
  );
  body.append(actionsRow);
  return modal;
}

function nextDateAfter(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}
