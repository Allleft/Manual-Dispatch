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
  const form = document.createElement("form");
  form.className = "workspace-delivery-closeout-form";
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = await actions.submitDeliveryRunSheetCloseout();
    if (result?.error && document.body.contains(form)) {
      form.querySelector(".workspace-status-error")?.remove();
      const status = createStatus(result.error, "error");
      status.classList.add("workspace-closeout-validation");
      actionsRow.before(status);
      firstInvalidCloseoutRow(draft)
        ?.querySelector("select, input, textarea")
        ?.focus();
    }
  });

  const summary = document.createElement("p");
  summary.className = "workspace-delivery-closeout-summary";
  summary.textContent = [
    draft.driver_name,
    draft.delivery_date,
    `${draft.rows.length} orders`,
  ].join(" | ");
  form.append(summary);

  const bulkActions = document.createElement("div");
  bulkActions.className = "workspace-action-row workspace-delivery-closeout-bulk";
  bulkActions.append(createActionButton(
    "Mark All Delivered",
    () => {
      const scrollBody = list.closest(".workspace-delivery-closeout-body");
      const scrollTop = scrollBody?.scrollTop || 0;
      actions.markAllDeliveryCloseoutRowsDelivered();
      list.querySelectorAll("[data-closeout-row-id]").forEach((card) => {
        const row = draft.rows.find(
          (item) => item.run_sheet_row_id === card.dataset.closeoutRowId,
        );
        patchDeliveryCloseoutCard(card, row, draft, actions);
      });
      if (scrollBody) {
        scrollBody.scrollTop = scrollTop;
      }
    },
    { disabled: isSubmitting },
  ));
  form.append(bulkActions);

  const list = document.createElement("div");
  list.className = "workspace-delivery-closeout-list";
  draft.rows.forEach((row) => {
    const card = document.createElement("section");
    card.className = "workspace-delivery-closeout-row";
    card.dataset.closeoutRowId = row.run_sheet_row_id;
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

    card.append(createDeliveryCloseoutFields(row, draft, actions, card));
    list.append(card);
  });
  form.append(list);

  if (draft.error) {
    form.append(createStatus(draft.error, "error"));
  }
  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row workspace-delivery-closeout-actions";
  actionsRow.append(
    createActionButton("Cancel", actions.closeDeliveryRunSheetCloseout, {
      disabled: isSubmitting,
    }),
    (() => {
      const submit = createActionButton(
      isSubmitting ? "Closing Run Sheet..." : "Review and Close",
      () => {},
      { disabled: isSubmitting, primary: true },
      );
      submit.type = "submit";
      return submit;
    })(),
  );
  form.append(actionsRow);
  body.append(form);
  return modal;
}

export function createDeliveryCloseoutFields(row, draft, actions, card) {
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
    (value) => {
      actions.updateDeliveryCloseoutRow(row.run_sheet_row_id, "outcome", value);
      patchDeliveryCloseoutCard(card, row, draft, actions);
    },
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
        (value) => {
          actions.updateDeliveryCloseoutRow(
            row.run_sheet_row_id,
            "reason_code",
            value,
          );
          const noteLabel = card.querySelector("textarea")?.closest("label")?.querySelector("span");
          if (noteLabel) {
            noteLabel.textContent = value === "OTHER" ? "Note (required)" : "Note (optional)";
          }
        },
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
  }
  fields.append(createBoundTextarea(
    row.outcome === "RETURN_TO_POOL" && row.reason_code === "OTHER"
      ? "Note (required)"
      : "Note (optional)",
    row.note,
    (value) => actions.updateDeliveryCloseoutRow(
      row.run_sheet_row_id,
      "note",
      value,
    ),
  ));
  return fields;
}

export function patchDeliveryCloseoutCard(card, row, draft, actions) {
  if (!card || !row) {
    return;
  }
  const current = card.querySelector(".workspace-delivery-closeout-fields");
  current?.replaceWith(createDeliveryCloseoutFields(row, draft, actions, card));
}

function firstInvalidCloseoutRow(draft) {
  const row = draft.rows.find((item) =>
    !item.outcome
    || (
      item.outcome === "RETURN_TO_POOL"
      && (
        !item.reason_code
        || !item.next_delivery_date
        || (item.reason_code === "OTHER" && !String(item.note || "").trim())
      )
    ));
  return row
    ? document.querySelector(`[data-closeout-row-id="${row.run_sheet_row_id}"]`)
    : null;
}

function nextDateAfter(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}
