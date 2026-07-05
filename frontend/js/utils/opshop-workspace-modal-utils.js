import { createIcon } from "./icon-utils.js";
import { formatOptional } from "./format-utils.js";


let opShopPickupDetailModalSequence = 0;


export function syncScopedOpShopModalState(state) {
  if (state.activeWorkspace !== "opshop" || !state.opshopBoard) {
    return false;
  }

  const pickups = state.opshopBoard.opshop_pickups || [];
  state.scheduledOpShopPickups = pickups.filter(
    (pickup) => pickup.run_type === "REGULAR",
  );
  state.oncallOpShopPickups = pickups.filter(
    (pickup) =>
      pickup.run_type === "ON_CALL" && pickup.pickup_category !== "COUNTRYSIDE",
  );
  state.countrysideOpShopPickups = pickups.filter(
    (pickup) => pickup.pickup_category === "COUNTRYSIDE",
  );
  state.countrysideRouteGroups = state.opshopBoard.countryside_route_groups || [];

  const regularDates = state.scheduledOpShopPickups
    .map((pickup) => pickup.pickup_date)
    .filter(Boolean)
    .sort();
  state.opshopRegularListWindowStart = regularDates[0] || state.dispatchDate;
  state.opshopRegularListWindowEnd = regularDates.at(-1) || state.dispatchDate;
  return true;
}

export function getOpShopModalDrivers(state) {
  if (state.activeWorkspace === "opshop") {
    return state.opshopBoard?.drivers || [];
  }
  return state.drivers;
}


export function openOpShopPickupDetailModal(host, { pickup, trigger }) {
  if (!host || !pickup) {
    return;
  }
  host.querySelector(".workspace-opshop-pickup-detail-backdrop")?.remove();
  opShopPickupDetailModalSequence += 1;
  const titleId = `workspace-opshop-pickup-detail-title-${opShopPickupDetailModalSequence}`;
  const backdrop = document.createElement("div");
  backdrop.className = "workspace-modal-backdrop workspace-opshop-pickup-detail-backdrop";
  const modal = document.createElement("article");
  modal.className = "workspace-modal workspace-modal-opshop-pickup-detail";
  modal.tabIndex = -1;
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", titleId);

  const requestClose = () => {
    backdrop.remove();
    if (
      trigger
      && typeof trigger.focus === "function"
      && typeof window !== "undefined"
      && typeof window.requestAnimationFrame === "function"
    ) {
      window.requestAnimationFrame(() => {
        if (document.body.contains(trigger)) {
          trigger.focus({ preventScroll: true });
        }
      });
    }
  };

  modal.addEventListener("click", (event) => event.stopPropagation());
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      requestClose();
    } else if (event.key === "Tab") {
      trapOpShopModalFocus(modal, event);
    }
  });

  const header = document.createElement("header");
  header.className = "workspace-modal-header";
  const titleGroup = document.createElement("div");
  titleGroup.className = "workspace-modal-title-group";
  const icon = document.createElement("span");
  icon.className = "workspace-modal-icon";
  icon.append(createIcon("store"));
  const copy = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "workspace-modal-eyebrow";
  eyebrow.textContent = "OP SHOP Pickup Details";
  const title = document.createElement("h3");
  title.id = titleId;
  title.textContent = formatOptional(pickup.opshop_name, "OP SHOP Pickup");
  const subtitle = document.createElement("p");
  subtitle.className = "workspace-modal-subtitle";
  subtitle.textContent = [pickup.suburb, pickup.pickup_date].filter(Boolean).join(" - ");
  copy.append(eyebrow, title, subtitle);
  titleGroup.append(icon, copy);
  const close = document.createElement("button");
  close.type = "button";
  close.className = "button-secondary workspace-action-button workspace-modal-close workspace-opshop-detail-close";
  const closeText = document.createElement("span");
  closeText.textContent = "Close";
  close.append(closeText, createIcon("x"));
  close.addEventListener("click", requestClose);
  header.append(titleGroup, close);

  const body = document.createElement("div");
  body.className = "workspace-modal-body workspace-opshop-pickup-detail-body";
  const summary = document.createElement("div");
  summary.className = "workspace-opshop-detail-summary";
  summary.append(createOpShopDetailBadge(opShopPickupCategoryLabel(pickup)));
  if (pickup.route_group_name) {
    summary.append(createOpShopDetailBadge(pickup.route_group_name));
  }
  body.append(
    summary,
    createOpShopDetailSection("General", [
      ["OP SHOP / company", pickup.opshop_name],
      ["Category", opShopPickupCategoryLabel(pickup)],
      ["Pickup date", pickup.pickup_date],
      ["Current assignee", pickup.assigned_driver_name || (opShopPickupDriverId(pickup) ? "Assigned" : "Unassigned")],
      ["Default driver", pickup.default_driver_name || pickup.default_driver_alias],
      ["Suburb", pickup.suburb],
      ["Area / region", pickup.area_region],
      ["Full address", [pickup.street_address, pickup.suburb].filter(Boolean).join(", ")],
    ]),
    createOpShopDetailSection("Collection / Schedule", [
      ["Frequency", pickup.pickup_frequency],
      ["Run day", pickup.run_day],
      ["Time window", pickup.time_window],
      ["Call before arrival", formatOpShopCallBeforeArrival(pickup)],
      ["Key required", pickup.key_required ? "Yes" : "No"],
      ["Trailer restriction", pickup.trailer_restriction],
    ]),
    createOpShopDetailSection("Contact / Access", [
      ["Contact name", pickup.primary_contact],
      ["Contact phone", pickup.primary_phone],
      ["Secondary contact", pickup.secondary_contact],
      ["Secondary phone", pickup.secondary_phone],
      ["Access instructions", pickup.access_type],
      ["Route group", pickup.route_group_name],
    ]),
  );
  const notes = [pickup.task_notes, pickup.status_notes].filter(Boolean).join("\n\n");
  if (notes) {
    body.append(createOpShopNotesSection(notes));
  }
  modal.append(header, body);
  backdrop.append(modal);
  host.append(backdrop);
  if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
    window.setTimeout(() => modal.focus(), 0);
  }
}


function createOpShopDetailSection(titleText, facts) {
  const availableFacts = facts.filter(([, value]) => hasOpShopDetailValue(value));
  if (!availableFacts.length) {
    return document.createDocumentFragment();
  }
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-opshop-detail-section";
  const title = document.createElement("h4");
  title.textContent = titleText;
  const list = document.createElement("dl");
  list.className = "workspace-modal-fact-grid workspace-opshop-detail-grid";
  availableFacts.forEach(([labelText, value]) => {
    const item = document.createElement("div");
    const label = document.createElement("dt");
    label.textContent = labelText;
    const detail = document.createElement("dd");
    detail.textContent = String(value);
    item.append(label, detail);
    list.append(item);
  });
  section.append(title, list);
  return section;
}


function createOpShopNotesSection(notes) {
  const section = document.createElement("section");
  section.className = "workspace-modal-section workspace-opshop-detail-section workspace-opshop-detail-notes-section";
  const title = document.createElement("h4");
  title.textContent = "Notes";
  const copy = document.createElement("p");
  copy.className = "workspace-opshop-detail-notes";
  copy.textContent = notes;
  section.append(title, copy);
  return section;
}


function createOpShopDetailBadge(labelText) {
  const badge = document.createElement("span");
  badge.className = "workspace-badge";
  badge.textContent = labelText;
  return badge;
}


function opShopPickupCategoryLabel(pickup) {
  if (pickup.pickup_category === "COUNTRYSIDE") {
    return "Countryside";
  }
  return pickup.run_type === "REGULAR" ? "Regular" : "Oncall";
}


function formatOpShopCallBeforeArrival(pickup) {
  if (!pickup.call_before_arrival) {
    return "No";
  }
  return ["Yes", pickup.call_timing].filter(Boolean).join(" - ");
}


function opShopPickupDriverId(pickup) {
  return pickup.assigned_driver_id || pickup.driver_id || "";
}


function hasOpShopDetailValue(value) {
  return value !== null && value !== undefined && String(value).trim() !== "";
}


function trapOpShopModalFocus(modal, event) {
  const focusable = Array.from(
    modal.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"),
  );
  if (!focusable.length) {
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
