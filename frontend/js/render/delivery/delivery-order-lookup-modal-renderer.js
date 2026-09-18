import { formatOptional } from "../../utils/format-utils.js";
import { createWorkspaceModal, createModalFactSection, createStatus } from "./delivery-renderer-utils.js";

export function createDeliveryOrderLookupModal(state, actions, existing = null) {
  const lookup = state.deliveryOrderLookup;
  if (!lookup?.open) return document.createDocumentFragment();
  const root = existing || createWorkspaceModal("Find Delivery Order", actions.closeDeliveryOrderLookup, {
    subtitle: "Search Manual Dispatch history by Invoice #. This does not query Attaché.",
    width: "invoice-lookup",
  });
  root.classList.add("delivery-order-lookup-backdrop");
  const body = root.querySelector(".workspace-modal-body");
  const scrollTop = body.scrollTop;
  if (!existing) {
    const form = document.createElement("form");
    form.className = "delivery-order-lookup-form";
    const label = document.createElement("label");
    label.className = "workspace-field";
    label.textContent = "Invoice #";
    const input = document.createElement("input");
    input.name = "invoice_number";
    input.type = "text";
    input.autocomplete = "off";
    input.required = true;
    label.append(input);
    const search = document.createElement("button");
    search.type = "submit";
    search.className = "primary-button";
    search.textContent = "Search";
    const results = document.createElement("div");
    results.className = "delivery-order-lookup-results";
    results.setAttribute("aria-live", "polite");
    input.addEventListener("input", () => {
      actions.updateDeliveryOrderLookupQuery(input.value);
      search.disabled = !input.value.trim();
      search.textContent = "Search";
      results.replaceChildren();
      results.setAttribute("aria-busy", "false");
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      actions.searchDeliveryOrderLookup();
    });
    form.append(label, search);
    body.append(form, results);
  }
  const input = body.querySelector("input");
  input.value = lookup.query;
  const search = body.querySelector("button[type='submit']");
  search.disabled = lookup.loading || !lookup.query.trim();
  search.textContent = lookup.loading ? "Searching…" : "Search";
  const results = body.querySelector(".delivery-order-lookup-results");
  results.replaceChildren();
  results.setAttribute("aria-busy", String(lookup.loading));
  if (lookup.loading) results.append(createStatus("Searching Manual Dispatch…", "loading"));
  if (lookup.error) {
    const error = createStatus(lookup.error, "error");
    error.setAttribute("role", "alert");
    results.append(error);
  }
  if (lookup.result) {
    const { invoice_number: invoice, match_count: count, orders } = lookup.result;
    if (!count) {
      results.append(createStatus(`No Manual Dispatch Order found for Invoice #${invoice}.`, "empty"));
    } else {
      if (count > 1) {
        results.append(createStatus(`${count} Manual Dispatch Orders found for Invoice #${invoice}. Review each match.`, "warning"));
      }
      orders.forEach((match) => results.append(createMatch(match)));
    }
  }
  body.scrollTop = scrollTop;
  if (typeof window !== "undefined") {
    window.setTimeout(() => {
      if (document.body.contains(root)) input.focus({ preventScroll: true });
    }, 0);
  }
  return root;
}

function createMatch(match) {
  const card = document.createElement("article");
  card.className = "delivery-order-lookup-match";
  const title = document.createElement("h4");
  title.textContent = `Invoice #${formatOptional(match.order.invoice_number)} — ${match.order.company_name}`;
  const badge = document.createElement("p");
  badge.className = "delivery-order-lookup-status";
  badge.dataset.status = match.current_status;
  badge.textContent = match.status_label;
  const order = match.order;
  card.append(title, badge, createModalFactSection("Order", [
    ["Order #", order.order_no], ["Manual Dispatch Order ID", match.order_id],
    ["Delivery Date", order.delivery_date], ["Persisted order status", order.status],
    ["Address", order.delivery_address], ["Suburb / Postcode", `${order.suburb || ""} ${order.postcode || ""}`],
    ["Pallets", order.pallet_quantity], ["Loose bags", order.loose_bags_quantity],
    ["Cartons", order.carton_quantity],
  ]));
  if (match.assignment) {
    const assignment = match.assignment;
    card.append(createModalFactSection("Current assignment", [
      ["Driver", assignment.driver_name || assignment.driver_id],
      ["Trip", tripLabel(assignment.trip_no)], ["Assignment dispatch date", assignment.dispatch_date],
    ]));
  }
  if (match.active_run_sheet) card.append(createRunSheetFacts("Current Run Sheet", match.active_run_sheet));
  if (match.latest_closeout) card.append(createRunSheetFacts("Latest closeout", match.latest_closeout));
  const history = document.createElement("details");
  const summary = document.createElement("summary");
  summary.tabIndex = 0;
  summary.textContent = `Run Sheet history (${match.run_sheet_history.length})`;
  history.append(summary);
  match.run_sheet_history.forEach((row) => history.append(createRunSheetFacts("Run Sheet", row)));
  if (!match.run_sheet_history.length) history.append(createStatus("No persisted Run Sheet history.", "empty"));
  card.append(history);
  return card;
}

function createRunSheetFacts(title, sheet) {
  const facts = [
    ["Run Sheet ID", sheet.run_sheet_id],
    ["Driver", sheet.driver_name_snapshot || sheet.driver_id],
    ["Vehicle", sheet.vehicle_rego_snapshot || sheet.vehicle_id],
    ["Delivery Date", sheet.delivery_date], ["Dispatch date", sheet.dispatch_date],
    ["Trip", tripLabel(sheet.trip_no)], ["Run Sheet status", sheet.status],
    ["Execution", sheet.execution_status], ["Generated", sheet.generated_at],
    ["Saved", sheet.saved_at],
  ];
  if (sheet.outcome) facts.push(
    ["Outcome", sheet.outcome], ["Reason", sheet.reason_code], ["Note", sheet.note],
    ["Next delivery date", sheet.next_delivery_date], ["Closed", sheet.closed_at],
    ["Recorded", sheet.recorded_at],
    ["Operator", sheet.recorded_by_account_name || sheet.closed_by_account_name],
  );
  return createModalFactSection(title, facts);
}

function tripLabel(value) {
  return value === "trip1" ? "Trip 1" : value === "trip2" ? "Trip 2" : formatOptional(value);
}
