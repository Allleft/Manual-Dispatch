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
  const modalShell = modal.querySelector(".workspace-modal");
  modalShell.classList.add("workspace-modal-delivery-closeout");
  const body = modal.querySelector(".workspace-modal-body");
  body.classList.add("workspace-delivery-closeout-body");
  body.dataset.deliveryCloseoutScrollContainer = "";
  const form = document.createElement("form");
  form.className = "workspace-delivery-closeout-form";
  form.id = "workspace-delivery-closeout-form";
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = await actions.submitDeliveryRunSheetCloseout();
    if (result?.error && document.body.contains(form)) {
      form.querySelector(".workspace-status-error")?.remove();
      draft.rows.forEach((row) => {
        const card = form.querySelector(
          `[data-closeout-row-id="${row.run_sheet_row_id}"]`,
        );
        patchDeliveryCloseoutValidation(card, row);
      });
      if (!result.validation) {
        const status = createStatus(result.error, "error");
        status.classList.add("workspace-closeout-validation");
        form.append(status);
      }
      firstInvalidCloseoutField(draft)?.focus();
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

    card.append(
      createDeliveryCloseoutFields(row, draft, actions, card),
      createDeliveryCloseoutValidation(row),
    );
    list.append(card);
  });
  form.append(list);

  if (draft.error) {
    form.append(createStatus(draft.error, "error"));
  }
  const actionsRow = document.createElement("div");
  actionsRow.className =
    "workspace-modal-footer workspace-delivery-closeout-actions";
  const cancel = createActionButton(
    "Cancel",
    actions.closeDeliveryRunSheetCloseout,
    { disabled: isSubmitting },
  );
  cancel.type = "button";
  const submit = createActionButton(
      isSubmitting ? "Closing Run Sheet..." : "Review and Close",
      () => {},
      { disabled: isSubmitting, primary: true },
  );
  submit.type = "submit";
  submit.setAttribute("form", form.id);
  actionsRow.append(cancel, submit);
  body.append(form);
  modalShell.append(actionsRow);
  return modal;
}

export function createDeliveryCloseoutFields(row, draft, actions, card) {
  const fields = document.createElement("div");
  fields.className = "workspace-form-grid workspace-delivery-closeout-fields";
  const outcomeField = createBoundSelect(
    "Outcome",
    row.outcome,
    [
      { value: "", label: "Choose outcome" },
      { value: "DELIVERED", label: "Delivered" },
      { value: "RETURN_TO_POOL", label: "Return to Delivery Task Pool" },
    ],
    (value) => {
      const scrollBody = card.closest(".workspace-delivery-closeout-body");
      const scrollTop = scrollBody?.scrollTop || 0;
      actions.updateDeliveryCloseoutRow(row.run_sheet_row_id, "outcome", value);
      patchDeliveryCloseoutCard(card, row, draft, actions);
      if (scrollBody) {
        scrollBody.scrollTop = scrollTop;
      }
      card.querySelector('[data-closeout-field="outcome"]')?.focus();
    },
  );
  outcomeField.querySelector("select").dataset.closeoutField = "outcome";
  fields.append(outcomeField);
  if (row.outcome === "RETURN_TO_POOL") {
    const reasonField = createBoundSelect(
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
          patchDeliveryCloseoutValidation(card, row);
          const noteLabel = card.querySelector("textarea")?.closest("label")?.querySelector("span");
          if (noteLabel) {
            noteLabel.textContent = value === "OTHER" ? "Note (required)" : "Note (optional)";
          }
        },
      );
    reasonField.querySelector("select").dataset.closeoutField = "reason_code";
    fields.append(reasonField);
    const dateField = document.createElement("label");
    dateField.className = "workspace-field";
    const dateLabel = document.createElement("span");
    dateLabel.textContent = "Next delivery date";
    const dateInput = document.createElement("input");
    dateInput.type = "date";
    dateInput.dataset.closeoutField = "next_delivery_date";
    dateInput.min = nextDateAfter(draft.delivery_date);
    dateInput.value = row.next_delivery_date || "";
    dateInput.addEventListener("change", () => {
      actions.updateDeliveryCloseoutRow(
        row.run_sheet_row_id,
        "next_delivery_date",
        dateInput.value,
      );
      patchDeliveryCloseoutValidation(card, row);
    });
    dateField.append(dateLabel, dateInput);
    fields.append(dateField);
  }
  const noteField = createBoundTextarea(
    row.outcome === "RETURN_TO_POOL" && row.reason_code === "OTHER"
      ? "Note (required)"
      : "Note (optional)",
    row.note,
    (value) => {
      actions.updateDeliveryCloseoutRow(
        row.run_sheet_row_id,
        "note",
        value,
      );
      patchDeliveryCloseoutValidation(card, row);
    },
  );
  noteField.querySelector("textarea").dataset.closeoutField = "note";
  fields.append(noteField);
  return fields;
}

export function patchDeliveryCloseoutCard(card, row, draft, actions) {
  if (!card || !row) {
    return;
  }
  const current = card.querySelector(".workspace-delivery-closeout-fields");
  current?.replaceWith(createDeliveryCloseoutFields(row, draft, actions, card));
  patchDeliveryCloseoutValidation(card, row);
}

export function patchDeliveryCloseoutValidation(card, row) {
  if (!card || !row) {
    return;
  }
  const current = card.querySelector(".workspace-delivery-closeout-validation");
  current?.replaceWith(createDeliveryCloseoutValidation(row));
}

function createDeliveryCloseoutValidation(row) {
  const validation = document.createElement("div");
  validation.className = "workspace-delivery-closeout-validation";
  validation.dataset.closeoutValidationFor = row.run_sheet_row_id;
  Object.entries(row.validation_errors || {}).forEach(([field, message]) => {
    const status = createStatus(message, "error");
    status.dataset.closeoutErrorFor = field;
    validation.append(status);
  });
  return validation;
}

function firstInvalidCloseoutField(draft) {
  const row = draft.rows.find(
    (item) => Object.keys(item.validation_errors || {}).length,
  );
  if (!row) {
    return null;
  }
  const card = document.querySelector(
    `[data-closeout-row-id="${row.run_sheet_row_id}"]`,
  );
  const field = Object.keys(row.validation_errors || {})[0];
  return card?.querySelector(`[data-closeout-field="${field}"]`) || null;
}

function nextDateAfter(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}
