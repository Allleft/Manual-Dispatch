import { createIcon } from "./icon-utils.js";
import { formatOptional } from "./format-utils.js";


let opShopDetailModalSequence = 0;


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
  const shell = createOpShopWorkspaceDetailModal(host, {
    className: "workspace-modal-opshop-pickup-detail",
    trigger,
  });
  const { body, modal, setHeader } = shell;
  setHeader({
    eyebrow: "OP SHOP Pickup Details",
    iconName: "store",
    subtitle: [pickup.suburb, pickup.pickup_date].filter(Boolean).join(" - "),
    title: formatOptional(pickup.opshop_name, "OP SHOP Pickup"),
  });
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
  focusOpShopModal(modal);
}


export function openCountrysideRouteGroupDetailModal(
  host,
  { group, templates = [], pickups = [], pickupDate = "", trigger },
) {
  if (!host || !group) {
    return;
  }
  const activeTemplates = templates.filter(isActiveCountrysideTemplate);
  const shell = createOpShopWorkspaceDetailModal(host, {
    className: "workspace-modal-opshop-route-detail",
    trigger,
  });
  const { body, modal, setHeader } = shell;

  const renderRouteGroup = (focusScheduleId = "") => {
    setHeader({
      eyebrow: "Countryside Route Group Details",
      iconName: "route",
      subtitle: `${activeTemplates.length} active route templates`,
      title: formatOptional(group.route_group_name, "Countryside Route Group"),
    });
    body.className = "workspace-modal-body workspace-opshop-route-detail-body";
    body.replaceChildren();
    const explanation = document.createElement("p");
    explanation.className = "workspace-opshop-route-detail-explanation";
    explanation.textContent = "Active countryside OP SHOP templates in this route group.";
    body.append(explanation);

    if (!activeTemplates.length) {
      body.append(createOpShopModalEmptyState(
        "No active OP SHOP templates are available in this route group.",
      ));
      return;
    }

    const list = document.createElement("div");
    list.className = "workspace-opshop-route-template-list";
    let focusTarget = null;
    activeTemplates.forEach((template) => {
      const row = createCountrysideTemplateRow(template, () => {
        renderTemplateDetail(template);
      });
      if (template.schedule_id === focusScheduleId) {
        focusTarget = row;
      }
      list.append(row);
    });
    body.append(list);
    if (focusTarget) {
      focusOpShopElement(focusTarget);
    }
  };

  const renderTemplateDetail = (template) => {
    const matchingTask = pickups.find((pickup) =>
      pickup.schedule_id === template.schedule_id
      && (!pickupDate || pickup.pickup_date === pickupDate),
    );
    setHeader({
      eyebrow: "Countryside OP SHOP Template Details",
      iconName: "store",
      subtitle: formatOptional(group.route_group_name),
      title: formatOptional(template.name, "OP SHOP Template"),
    });
    body.className = "workspace-modal-body workspace-opshop-route-detail-body";
    body.replaceChildren();
    const back = document.createElement("button");
    back.type = "button";
    back.className = "button-secondary workspace-action-button workspace-opshop-route-back";
    back.append(createIcon("arrow-right", "workspace-opshop-route-back-icon"));
    const backLabel = document.createElement("span");
    backLabel.textContent = "Back to Route Group";
    back.append(backLabel);
    back.addEventListener("click", () => renderRouteGroup(template.schedule_id));
    const actions = document.createElement("div");
    actions.className = "workspace-modal-action-bar workspace-opshop-route-detail-actions";
    actions.append(back);
    body.append(
      actions,
      createOpShopDetailSection("General", [
        ["OP SHOP / company", template.name],
        ["Category", "Countryside"],
        ["Route group", group.route_group_name],
        ["Suburb", template.suburb],
        ["Area / region", template.area_region],
        ["Full address", [template.street_address, template.suburb].filter(Boolean).join(", ")],
        ["Template status", template.status],
      ]),
      createOpShopDetailSection("Collection / Schedule", [
        ["Frequency", template.pickup_frequency],
        ["Run day", template.run_day],
        ["Time window", template.time_window],
        ["Default driver", template.default_driver_name || template.default_driver_alias],
        ["Template context", "ON_CALL + COUNTRYSIDE"],
        ["Actual pickup status", matchingTask?.status],
        ["Actual assignee", matchingTask?.assigned_driver_name],
      ]),
      createOpShopDetailSection("Contact / Access", [
        ["Contact name", template.primary_contact],
        ["Contact phone", template.primary_phone],
        ["Secondary contact", template.secondary_contact],
        ["Secondary phone", template.secondary_phone],
        ["Call before arrival", formatOpShopCallBeforeArrival(template)],
        ["Access instructions", template.access_type],
        ["Key required", template.key_required ? "Yes" : "No"],
        ["Trailer restriction", template.trailer_restriction],
      ]),
    );
    if (template.status_notes) {
      body.append(createOpShopNotesSection(template.status_notes));
    }
    focusOpShopModal(modal);
  };

  renderRouteGroup();
  focusOpShopModal(modal);
}


function createOpShopWorkspaceDetailModal(host, { className, trigger }) {
  host.querySelector(".workspace-opshop-detail-backdrop")?.remove();
  opShopDetailModalSequence += 1;
  const titleId = `workspace-opshop-detail-title-${opShopDetailModalSequence}`;
  const backdrop = document.createElement("div");
  backdrop.className = "workspace-modal-backdrop workspace-opshop-detail-backdrop";
  const modal = document.createElement("article");
  modal.className = `workspace-modal ${className}`;
  modal.tabIndex = -1;
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", titleId);

  const requestClose = () => {
    backdrop.remove();
    if (trigger && typeof trigger.focus === "function") {
      focusOpShopElement(trigger, true);
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
  const copy = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "workspace-modal-eyebrow";
  const title = document.createElement("h3");
  title.id = titleId;
  const subtitle = document.createElement("p");
  subtitle.className = "workspace-modal-subtitle";
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
  body.className = "workspace-modal-body";
  modal.append(header, body);
  backdrop.append(modal);
  host.append(backdrop);

  return {
    body,
    modal,
    requestClose,
    setHeader({ eyebrow: eyebrowText, iconName, subtitle: subtitleText, title: titleText }) {
      icon.replaceChildren(createIcon(iconName));
      eyebrow.textContent = eyebrowText;
      title.textContent = titleText;
      subtitle.textContent = subtitleText || "";
      subtitle.hidden = !subtitleText;
    },
  };
}


function createCountrysideTemplateRow(template, onOpen) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "workspace-opshop-route-template-row";
  row.setAttribute(
    "aria-label",
    `View Countryside OP SHOP template details for ${formatOptional(template.name)}`,
  );
  const identity = document.createElement("span");
  identity.className = "workspace-opshop-route-template-identity";
  const name = document.createElement("strong");
  name.textContent = formatOptional(template.name);
  const location = document.createElement("span");
  location.textContent = [template.street_address, template.suburb]
    .filter(Boolean)
    .join(", ") || "Address not recorded";
  const schedule = document.createElement("span");
  schedule.textContent = [
    template.pickup_frequency,
    template.run_day,
    template.status,
  ].filter(Boolean).join(" - ");
  identity.append(name, location, schedule);
  const affordance = document.createElement("span");
  affordance.className = "workspace-opshop-route-template-affordance";
  affordance.append(createIcon("arrow-right"));
  row.append(identity, affordance);
  row.addEventListener("click", onOpen);
  return row;
}


function createOpShopModalEmptyState(message) {
  const empty = document.createElement("div");
  empty.className = "workspace-empty-state workspace-opshop-route-detail-empty";
  empty.append(createIcon("store"));
  const copy = document.createElement("p");
  copy.textContent = message;
  empty.append(copy);
  return empty;
}


function isActiveCountrysideTemplate(template) {
  return Boolean(
    template
    && template.pickup_category === "COUNTRYSIDE"
    && template.active_flag !== false
    && template.status !== "On_Hold",
  );
}


function focusOpShopModal(modal) {
  if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
    window.setTimeout(() => modal.focus(), 0);
  }
}


function focusOpShopElement(element, requireConnected = false) {
  if (
    !element
    || typeof element.focus !== "function"
    || typeof window === "undefined"
    || typeof window.requestAnimationFrame !== "function"
  ) {
    return;
  }
  window.requestAnimationFrame(() => {
    if (!requireConnected || document.body.contains(element)) {
      element.focus({ preventScroll: true });
    }
  });
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
