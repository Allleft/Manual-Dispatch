import { createIcon } from "../utils/icon-utils.js";
import { formatOptional } from "../utils/format-utils.js";


const OPSHOP_TABS = [
  { route: "opshop/regular", label: "Regular" },
  { route: "opshop/oncall", label: "Oncall" },
  { route: "opshop/countryside", label: "Countryside" },
  { route: "opshop/templates", label: "Templates" },
  { route: "opshop/collections", label: "Pickup Collections" },
  { route: "opshop/history", label: "Saved History" },
];


export function renderOpShopWorkspace(root, { state, onDispatchDateChange }) {
  root.innerHTML = "";
  const page = createWorkspacePage(state, onDispatchDateChange);
  const content = document.createElement("div");
  content.className = "workspace-content";

  if (state.isOpShopWorkspaceLoading) {
    content.append(createStatus("Loading OP SHOP Pickup workspace...", "loading"));
  } else if (state.opshopWorkspaceError) {
    content.append(createStatus(state.opshopWorkspaceError, "error"));
  } else if (state.workspaceRoute === "opshop/templates") {
    content.append(createTemplateList(state.opshopBoard));
  } else if (
    state.workspaceRoute === "opshop/collections" ||
    state.workspaceRoute === "opshop/history"
  ) {
    content.append(
      createCollectionList(
        state.opshopPickupCollections,
        state.workspaceRoute === "opshop/history",
      ),
    );
  } else {
    content.append(createPickupList(state.opshopBoard, state.workspaceRoute));
  }

  page.append(content);
  root.append(page);
}


function createWorkspacePage(state, onDispatchDateChange) {
  const page = document.createElement("section");
  page.className = "workspace-page workspace-page-opshop";

  const heading = document.createElement("header");
  heading.className = "workspace-page-heading";
  const titleGroup = document.createElement("div");
  titleGroup.className = "workspace-page-title-group";
  const icon = document.createElement("span");
  icon.className = "workspace-page-icon";
  icon.append(createIcon("store"));
  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Pickup workspace";
  const title = document.createElement("h2");
  title.textContent = "OP SHOP Pickup";
  const description = document.createElement("p");
  description.textContent = "Review pickup activity, templates, route context, and independent saved collections.";
  copy.append(kicker, title, description);
  titleGroup.append(icon, copy);
  heading.append(titleGroup, createDateControl(state, onDispatchDateChange));

  const nav = document.createElement("nav");
  nav.className = "workspace-tabs workspace-tabs-opshop";
  nav.setAttribute("aria-label", "OP SHOP Pickup workspace");
  OPSHOP_TABS.forEach((tab) => nav.append(createTab(tab, state.workspaceRoute)));

  const notice = createStatus(
    "Workspace actions will be enabled in the next implementation stage.",
    "notice",
  );
  page.append(heading, nav, notice);
  return page;
}


function createDateControl(state, onDispatchDateChange) {
  const label = document.createElement("label");
  label.className = "workspace-date-control";
  label.textContent = "Dispatch date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = state.dispatchDate;
  input.disabled = state.isOpShopWorkspaceLoading;
  input.addEventListener("change", () => onDispatchDateChange(input.value));
  label.append(input);
  return label;
}


function createTab(tab, activeRoute) {
  const link = document.createElement("a");
  link.href = `#${tab.route}`;
  link.className = "workspace-tab";
  link.textContent = tab.label;
  if (tab.route === activeRoute) {
    link.classList.add("workspace-tab-active");
    link.setAttribute("aria-current", "page");
  }
  return link;
}


function createPickupList(board, route) {
  if (!board) {
    return createEmptyState("No OP SHOP workspace data loaded.", "store");
  }
  const pickups = (board.opshop_pickups || []).filter((pickup) => {
    if (route === "opshop/regular") {
      return pickup.run_type === "REGULAR";
    }
    if (route === "opshop/countryside") {
      return pickup.pickup_category === "COUNTRYSIDE";
    }
    return pickup.run_type === "ON_CALL" && pickup.pickup_category !== "COUNTRYSIDE";
  });
  const context = getPickupRouteContext(route);
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  wrapper.append(
    createMetricGrid([
      [context.title, pickups.length, context.icon],
      ["Assigned", pickups.filter((pickup) => pickup.is_assigned).length, "user"],
      ["Unassigned", pickups.filter((pickup) => !pickup.is_assigned).length, "store"],
      ["Active route groups", (board.countryside_route_groups || []).length, "route"],
    ]),
    createSectionHeading(context.heading, context.description),
  );

  if (route === "opshop/countryside") {
    wrapper.append(createRouteGroupContext(board.countryside_route_groups || []));
  }

  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-pickup-grid";
  if (!pickups.length) {
    grid.append(createEmptyState(context.emptyMessage, context.icon));
  } else {
    pickups.forEach((pickup) => grid.append(createPickupCard(pickup)));
  }
  wrapper.append(grid);
  return wrapper;
}


function getPickupRouteContext(route) {
  if (route === "opshop/regular") {
    return {
      title: "Regular pickups",
      heading: "Regular Pickup Schedule",
      description: "Active scheduled pickup tasks for the current board window",
      emptyMessage: "No Regular pickups are visible for this dispatch date.",
      icon: "calendar",
    };
  }
  if (route === "opshop/countryside") {
    return {
      title: "Countryside pickups",
      heading: "Countryside Route Pickups",
      description: "Active countryside pickup tasks with route-group context",
      emptyMessage: "No Countryside pickups are visible for this dispatch date.",
      icon: "tree",
    };
  }
  return {
    title: "Oncall pickups",
    heading: "Oncall Pickup Requests",
    description: "Actual request-driven pickup tasks created by office staff",
    emptyMessage: "No Oncall pickups are visible for this dispatch date.",
    icon: "phone",
  };
}


function createPickupCard(pickup) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-pickup-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.className = "workspace-record-kicker";
  kicker.textContent = pickup.pickup_category === "COUNTRYSIDE"
    ? formatOptional(pickup.route_group_name, "Countryside")
    : formatOptional(pickup.run_type);
  const title = document.createElement("h3");
  title.textContent = formatOptional(pickup.opshop_name);
  const location = document.createElement("p");
  location.textContent = [pickup.street_address, pickup.suburb].filter(Boolean).join(", ");
  identity.append(kicker, title, location);
  top.append(identity, createBadge(formatOptional(pickup.status, "ACTIVE")));

  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Pickup date", pickup.pickup_date);
  appendFact(facts, "Assigned driver", pickup.assigned_driver_name || pickup.driver_id || "Unassigned");
  appendFact(facts, "Default driver", pickup.default_driver_name || pickup.default_driver_alias || "None");
  appendFact(facts, "Time window", pickup.time_window);
  appendFact(facts, "Contact", joinValues(pickup.primary_contact, pickup.primary_phone));
  appendFact(facts, "Call before arrival", pickup.call_before_arrival ? formatOptional(pickup.call_timing, "Yes") : "No");
  appendFact(facts, "Access", pickup.access_type);
  appendFact(facts, "Key required", pickup.key_required ? "Yes" : "No");
  appendFact(facts, "Trailer restriction", pickup.trailer_restriction);
  appendFact(facts, "Notes", joinValues(pickup.task_notes, pickup.status_notes));
  card.append(top, facts);
  return card;
}


function createRouteGroupContext(routeGroups) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-opshop";
  section.append(
    createSectionHeading(
      "Route Group Context",
      `${routeGroups.length} active countryside route groups`,
    ),
  );
  const list = document.createElement("div");
  list.className = "workspace-route-chip-list";
  routeGroups.forEach((group) => {
    const chip = document.createElement("span");
    chip.className = "workspace-route-chip";
    chip.append(createIcon("route"), document.createTextNode(group.route_group_name));
    list.append(chip);
  });
  if (!list.children.length) {
    list.append(createEmptyState("No active Countryside route groups.", "route"));
  }
  section.append(list);
  return section;
}


function createTemplateList(board) {
  if (!board) {
    return createEmptyState("No OP SHOP template data loaded.", "store");
  }
  const templates = board.templates || [];
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  wrapper.append(
    createSectionHeading(
      "OP SHOP Templates",
      `${templates.length} active Regular, Oncall, and Countryside templates`,
    ),
  );
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-template-grid";
  if (!templates.length) {
    grid.append(createEmptyState("No active OP SHOP templates are available.", "store"));
  } else {
    templates.forEach((template) => grid.append(createTemplateCard(template)));
  }
  wrapper.append(grid);
  return wrapper;
}


function createTemplateCard(template) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-template-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.className = "workspace-record-kicker";
  kicker.textContent = template.pickup_category === "COUNTRYSIDE"
    ? formatOptional(template.route_group_name, "Countryside")
    : formatOptional(template.run_type);
  const title = document.createElement("h3");
  title.textContent = formatOptional(template.opshop_name || template.name);
  const location = document.createElement("p");
  location.textContent = [template.street_address, template.suburb].filter(Boolean).join(", ");
  identity.append(kicker, title, location);
  top.append(identity, createBadge(formatOptional(template.status, "Active")));
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Run day", template.run_day || "No fixed day");
  appendFact(facts, "Frequency", template.pickup_frequency);
  appendFact(facts, "Time window", template.time_window);
  appendFact(facts, "Default driver", template.default_driver_name || template.default_driver_alias || "None");
  appendFact(facts, "Contact", joinValues(template.primary_contact, template.primary_phone));
  appendFact(facts, "Access", template.access_type);
  card.append(top, facts);
  return card;
}


function createCollectionList(collections, savedOnly) {
  const filtered = (collections || []).filter(
    (collection) => !savedOnly || collection.status === "SAVED",
  );
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  wrapper.append(
    createSectionHeading(
      savedOnly ? "Saved Pickup Collection History" : "OP SHOP Pickup Collections",
      `${filtered.length} ${savedOnly ? "saved records" : "generated and saved records"}`,
    ),
  );
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-collection-grid";
  if (!filtered.length) {
    grid.append(
      createEmptyState(
        savedOnly ? "No saved Pickup Collections for this dispatch date." : "No Pickup Collections for this dispatch date.",
        "history",
      ),
    );
  } else {
    filtered.forEach((collection) => grid.append(createCollectionCard(collection)));
  }
  wrapper.append(grid);
  return wrapper;
}


function createCollectionCard(collection) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-collection-card";
  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const kicker = document.createElement("span");
  kicker.className = "workspace-record-kicker";
  kicker.textContent = collection.pickup_date;
  const title = document.createElement("h3");
  title.textContent = formatOptional(collection.driver_name_snapshot, collection.driver_id);
  identity.append(kicker, title);
  top.append(identity, createBadge(collection.status));
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Pickup count", (collection.pickups || []).length);
  appendFact(facts, "Generated", collection.generated_at);
  appendFact(facts, "Saved", collection.saved_at || "Not saved");
  appendFact(facts, "Saved by", collection.saved_by_account_name || "Not saved");
  card.append(top, facts);
  return card;
}


function createMetricGrid(metrics) {
  const grid = document.createElement("div");
  grid.className = "workspace-metric-grid workspace-metric-grid-opshop";
  metrics.forEach(([label, value, iconName]) => {
    const card = document.createElement("div");
    card.className = "workspace-metric-card";
    card.append(createIcon(iconName));
    const copy = document.createElement("div");
    const number = document.createElement("strong");
    number.textContent = String(value);
    const text = document.createElement("span");
    text.textContent = label;
    copy.append(number, text);
    card.append(copy);
    grid.append(card);
  });
  return grid;
}


function createSectionHeading(titleText, descriptionText) {
  const heading = document.createElement("div");
  heading.className = "workspace-section-heading";
  const title = document.createElement("h3");
  title.textContent = titleText;
  const description = document.createElement("p");
  description.textContent = descriptionText;
  heading.append(title, description);
  return heading;
}


function appendFact(list, labelText, value) {
  const item = document.createElement("div");
  const label = document.createElement("dt");
  label.textContent = labelText;
  const detail = document.createElement("dd");
  detail.textContent = formatOptional(value);
  item.append(label, detail);
  list.append(item);
}


function createBadge(label) {
  const badge = document.createElement("span");
  badge.className = "workspace-badge";
  badge.textContent = label;
  return badge;
}


function createStatus(message, type) {
  const status = document.createElement("p");
  status.className = `workspace-status workspace-status-${type}`;
  if (type === "error") {
    status.setAttribute("role", "alert");
  } else {
    status.setAttribute("aria-live", "polite");
  }
  status.textContent = message;
  return status;
}


function createEmptyState(message, iconName) {
  const empty = document.createElement("div");
  empty.className = "workspace-empty-state";
  empty.append(createIcon(iconName));
  const text = document.createElement("p");
  text.textContent = message;
  empty.append(text);
  return empty;
}


function joinValues(...values) {
  return values.filter(Boolean).join(" · ") || "-";
}
