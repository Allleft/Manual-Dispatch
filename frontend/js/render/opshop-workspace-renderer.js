import { createIcon } from "../utils/icon-utils.js";
import { formatOptional } from "../utils/format-utils.js";
import { createOpShopTemplateManagementPanel } from "./opshop-template-management-modal-renderer.js";
import { createCountrysideRouteManagementPanel } from "./opshop-countryside-pickup-list-modal-renderer.js";


const OPSHOP_TABS = [
  { route: "opshop/task-pool/regular", label: "Task Pool" },
  { route: "opshop/trip-summary", label: "Trip Summary" },
  { route: "opshop/collections", label: "Pickup Collections" },
];
const OPSHOP_TASK_POOL_VIEWS = [
  { view: "regular", label: "Regular" },
  { view: "oncall", label: "Oncall" },
  { view: "countryside", label: "Countryside" },
];


export function renderOpShopWorkspace(
  root,
  { state, actions, onDispatchDateChange },
) {
  root.innerHTML = "";
  const page = createWorkspacePage(state, onDispatchDateChange);
  const content = document.createElement("div");
  content.className = "workspace-content";

  if (state.isOpShopWorkspaceLoading) {
    content.append(createStatus("Loading OP SHOP Pickup workspace...", "loading"));
  } else if (state.opshopWorkspaceError) {
    content.append(createStatus(state.opshopWorkspaceError, "error"));
  } else {
    if (state.opshopActionError) {
      content.append(createStatus(state.opshopActionError, "error"));
    }
    if (state.workspaceRoute === "opshop/templates") {
      content.append(createTemplateManagementPage(state, actions));
    } else if (state.workspaceRoute === "opshop/trip-summary") {
      content.append(createOpShopTripSummary(
        state.opshopBoard,
        state.opshopPickupCollections,
        state,
        actions,
      ));
    } else if (state.workspaceRoute === "opshop/collections") {
      content.append(
        createCollectionList(
          state.opshopPickupCollections,
          state,
          actions,
        ),
      );
    } else {
      content.append(createOpShopTaskPool(state.opshopBoard, state, actions));
    }
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
  description.textContent = "Assign pickups and manage independent saved pickup collections.";
  copy.append(kicker, title, description);
  titleGroup.append(icon, copy);
  heading.append(titleGroup, createDateControl(state, onDispatchDateChange));

  const nav = document.createElement("nav");
  nav.className = "workspace-tabs workspace-tabs-opshop";
  nav.setAttribute("aria-label", "OP SHOP Pickup workspace");
  const activeRoute = state.workspaceRoute === "opshop/templates"
    || state.workspaceRoute.startsWith("opshop/task-pool/")
    ? "opshop/task-pool/regular"
    : state.workspaceRoute;
  OPSHOP_TABS.forEach((tab) => nav.append(createTab(tab, activeRoute)));

  page.append(heading, nav);
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


function createOpShopTaskPool(board, state, actions) {
  if (!board) {
    return createEmptyState("No OP SHOP workspace data loaded.", "store");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-opshop-task-pool";
  const toolbar = document.createElement("section");
  toolbar.className = "workspace-context-panel workspace-context-panel-opshop workspace-opshop-task-pool-toolbar";
  const heading = createSectionHeading(
    "OP SHOP Pickup Task Pool",
    "Assign Regular, Oncall, and Countryside pickups before reviewing them by driver.",
  );
  const manageTemplates = createRouteActionLink(
    "Manage Templates",
    "#opshop/templates",
  );
  toolbar.append(heading, manageTemplates);

  const tabs = document.createElement("div");
  tabs.className = "workspace-subtabs workspace-subtabs-opshop";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "OP SHOP Task Pool pickup type");
  OPSHOP_TASK_POOL_VIEWS.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "workspace-subtab";
    button.textContent = item.label;
    const isActive = item.view === (state.opshopTaskPoolView || "regular");
    button.classList.toggle("workspace-subtab-active", isActive);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", isActive ? "true" : "false");
    button.addEventListener("click", () => actions.updateOpShopTaskPoolView(item.view));
    tabs.append(button);
  });
  wrapper.append(
    toolbar,
    tabs,
    createPickupList(board, state.opshopTaskPoolView || "regular", state, actions),
  );
  return wrapper;
}


function createPickupList(board, route, state, actions) {
  if (!board) {
    return createEmptyState("No OP SHOP workspace data loaded.", "store");
  }
  const pickups = pickupListForRoute(board, route);
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

  if (route === "regular" || route === "oncall") {
    const taskActions = document.createElement("div");
    taskActions.className = "workspace-action-row workspace-task-operation-toolbar";
    taskActions.append(
      createActionButton(
        "Add Pickup Task",
        () => actions.startAddOpShopPickupTask(route),
        { primary: true },
      ),
    );
    wrapper.append(taskActions);
  }

  if (route === "countryside") {
    wrapper.append(createRouteGroupContext(board, state, actions));
  }

  wrapper.append(createAssignmentApplyBar(pickups, state, actions));

  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-pickup-grid";
  if (!pickups.length) {
    grid.append(createEmptyState(context.emptyMessage, context.icon));
  } else {
    pickups.forEach((pickup) => grid.append(createPickupCard(pickup, state, actions)));
  }
  wrapper.append(grid);
  return wrapper;
}


function pickupListForRoute(board, route) {
  return (board.opshop_pickups || []).filter((pickup) => {
    if (route === "regular") {
      return pickup.run_type === "REGULAR";
    }
    if (route === "countryside") {
      return pickup.pickup_category === "COUNTRYSIDE";
    }
    return pickup.run_type === "ON_CALL" && pickup.pickup_category !== "COUNTRYSIDE";
  });
}


function getPickupRouteContext(route) {
  if (route === "regular") {
    return {
      title: "Regular pickups",
      heading: "Regular Pickup Schedule",
      description: "Active scheduled pickup tasks for the current board window",
      emptyMessage: "No Regular pickups are visible for this dispatch date.",
      icon: "calendar",
    };
  }
  if (route === "countryside") {
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


function createAssignmentApplyBar(pickups, state, actions) {
  const bar = document.createElement("section");
  bar.className = "workspace-context-panel workspace-context-panel-opshop workspace-assignment-bar";
  const changedCount = changedOpShopAssignments(pickups, state).length;
  const copy = document.createElement("div");
  const heading = document.createElement("strong");
  heading.textContent = "Assignment changes";
  const detail = document.createElement("span");
  detail.textContent = `${changedCount} pending changes`;
  copy.append(heading, detail);
  const button = createActionButton(
    "Apply Assignment Changes",
    () => actions.applyOpShopAssignmentChanges(pickups),
    {
      disabled: changedCount === 0 || isBusy(state, "opshop-apply-assignments"),
      primary: true,
    },
  );
  bar.append(copy, button);
  return bar;
}


function createPickupCard(pickup, state, actions) {
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
  appendFact(facts, "Current assignee", pickup.assigned_driver_name || pickup.driver_id || "Unassigned");
  appendFact(facts, "Suggested default", defaultDriverHint(pickup, state));
  appendFact(facts, "Time window", pickup.time_window);
  appendFact(facts, "Contact", joinValues(pickup.primary_contact, pickup.primary_phone));
  appendFact(facts, "Call before arrival", pickup.call_before_arrival ? formatOptional(pickup.call_timing, "Yes") : "No");
  appendFact(facts, "Access", pickup.access_type);
  appendFact(facts, "Key required", pickup.key_required ? "Yes" : "No");
  appendFact(facts, "Trailer restriction", pickup.trailer_restriction);
  appendFact(facts, "Notes", joinValues(pickup.task_notes, pickup.status_notes));

  const controls = createPickupAssignmentControls(pickup, state, actions);
  const taskActions = document.createElement("div");
  taskActions.className = "workspace-action-row workspace-pickup-task-actions";
  taskActions.append(
    createActionButton(
      "View details",
      () => actions.openOpShopPickupDetail(pickup.pickup_task_id),
    ),
    createActionButton(
      "Edit",
      () => actions.startEditOpShopPickupTask(pickup),
      { disabled: Boolean(pickup.assigned_to_locked) },
    ),
    createActionButton(
      "Delete",
      () => actions.startDeleteOpShopPickupTask(pickup),
      { disabled: Boolean(pickup.assigned_to_locked) },
    ),
  );
  card.append(top, facts, controls, taskActions);
  return card;
}


function createPickupAssignmentControls(pickup, state, actions) {
  const controls = document.createElement("div");
  controls.className = "workspace-action-row";
  const selectedDriverId = selectedOpShopDriverId(pickup, state);
  const driverSelect = createSelect(
    "Assigned to",
    selectedDriverId,
    [{ value: "", label: "Unassigned" }].concat(
      (state.opshopBoard?.drivers || []).map((driver) => ({
        value: driver.driver_id,
        label: driver.name,
      })),
    ),
    (value) => actions.updateOpShopAssignmentDraft(pickup.pickup_task_id, value),
  );
  driverSelect.querySelector("select").disabled = Boolean(pickup.assigned_to_locked);
  controls.append(driverSelect);
  if (pickup.is_assigned) {
    controls.append(
      createActionButton(
        "Unassign now",
        () => actions.unassignOpShopPickup(pickup.pickup_task_id),
        {
          disabled: pickup.assigned_to_locked || isBusy(state, `opshop-unassign:${pickup.pickup_task_id}`),
        },
      ),
    );
  }
  return controls;
}


function createRouteGroupContext(board, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-opshop";
  section.append(
    createSectionHeading(
      "Route Group Context",
      `${(board.countryside_route_groups || []).length} active countryside route groups`,
    ),
  );
  const list = document.createElement("div");
  list.className = "workspace-route-assignment-list";
  const routeTemplates = templatesByRouteGroup(board);
  (board.countryside_route_groups || []).forEach((group) => {
    list.append(createRouteGroupAssignmentForm(group, routeTemplates, state, actions));
  });
  if (!list.children.length) {
    list.append(createEmptyState("No active Countryside route groups.", "route"));
  }
  section.append(list);
  return section;
}


function createRouteGroupAssignmentForm(group, routeTemplates, state, actions) {
  const row = document.createElement("article");
  row.className = "workspace-record-card workspace-route-group-card";
  const templateCount = (routeTemplates.get(group.route_group_id) || []).length;
  const draft = {
    pickup_date: state.dispatchDate,
    assigned_driver_id: "",
    notes: "",
    ...(state.countrysideRouteGroupDrafts[group.route_group_id] || {}),
  };
  const title = document.createElement("h3");
  title.textContent = group.route_group_name;
  const meta = document.createElement("p");
  meta.textContent = `${templateCount} active route templates`;
  const controls = document.createElement("div");
  controls.className = "workspace-action-row workspace-action-row-stacked";
  controls.append(
    createDateField(
      "Pickup date",
      draft.pickup_date,
      (value) => actions.updateCountrysideRouteGroupDraft(
        group.route_group_id,
        "pickup_date",
        value,
      ),
    ),
    createSelect(
      "Assigned to",
      draft.assigned_driver_id,
      [{ value: "", label: "Select driver" }].concat(
        (state.opshopBoard?.drivers || []).map((driver) => ({
          value: driver.driver_id,
          label: driver.name,
        })),
      ),
      (value) => actions.updateCountrysideRouteGroupDraft(
        group.route_group_id,
        "assigned_driver_id",
        value,
      ),
    ),
    createTextField(
      "Notes",
      draft.notes,
      (value) => actions.updateCountrysideRouteGroupDraft(
        group.route_group_id,
        "notes",
        value,
      ),
    ),
  );
  const assignButton = createActionButton(
    "Assign Route Group",
    () => actions.assignCountrysideRouteGroup(group.route_group_id),
    {
      disabled:
        templateCount === 0 ||
        !draft.pickup_date ||
        !draft.assigned_driver_id ||
        isBusy(state, `opshop-route-group:${group.route_group_id}`),
      primary: true,
    },
  );
  if (templateCount === 0) {
    const warning = document.createElement("p");
    warning.className = "workspace-status workspace-status-notice";
    warning.textContent = "This route group has no active route templates.";
    row.append(title, meta, warning, controls, assignButton);
  } else {
    row.append(title, meta, controls, assignButton);
  }
  return row;
}


function createTemplateManagementPage(state, actions) {
  if (!state.opshopBoard) {
    return createEmptyState("No OP SHOP template data loaded.", "store");
  }
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack";
  const toolbar = document.createElement("section");
  toolbar.className = "workspace-context-panel workspace-context-panel-opshop workspace-template-toolbar";
  toolbar.append(
    createSectionHeading(
      "Manage OP SHOP Templates",
      "Add, edit, review, and soft-disable Regular and Oncall templates.",
    ),
    createRouteActionLink(
      "Back to Task Pool",
      `#${state.opshopTaskPoolReturnRoute || "opshop/task-pool/regular"}`,
    ),
  );
  wrapper.append(
    toolbar,
    createOpShopTemplateManagementPanel({
      onCancelForm: actions.cancelTemplateForm,
      onConfirmDisable: actions.disableTemplate,
      onSave: actions.saveTemplate,
      onSelectTab: actions.selectTemplateTab,
      onStartAdd: actions.startAddTemplate,
      onStartDisable: actions.startDisableTemplate,
      onStartEdit: actions.startEditTemplate,
      onToggleIncludeInactive: actions.toggleTemplateIncludeInactive,
      onUpdateForm: actions.updateTemplateForm,
    }),
    createSectionHeading(
      "Countryside Route Management",
      "Create and maintain route groups and their ON_CALL + COUNTRYSIDE template memberships.",
    ),
    createCountrysideRouteManagementPanel({
      onAddRouteTemplate: actions.addCountrysideRouteTemplate,
      onCancelRouteGroupForm: actions.cancelCountrysideRouteGroupForm,
      onCancelRouteTemplateForm: actions.cancelCountrysideRouteTemplateForm,
      onCloseRouteTemplateDetail: actions.closeCountrysideRouteTemplateDetail,
      onCreateRouteGroup: actions.createCountrysideRouteGroup,
      onDisableRouteGroup: actions.disableCountrysideRouteGroup,
      onMoveRouteTemplate: actions.moveCountrysideRouteTemplate,
      onOpenRouteTemplateDetail: actions.openCountrysideRouteTemplateDetail,
      onRemoveRouteTemplate: actions.removeCountrysideRouteTemplate,
      onRenameRouteGroup: actions.renameCountrysideRouteGroup,
      onSelectRouteGroup: actions.selectCountrysideRouteGroup,
      onStartAddRouteTemplate: actions.startAddCountrysideRouteTemplate,
      onStartDisableRouteGroup: actions.startDisableCountrysideRouteGroup,
      onStartMoveRouteTemplate: actions.startMoveCountrysideRouteTemplate,
      onStartNewRouteGroup: actions.startNewCountrysideRouteGroup,
      onStartRemoveRouteTemplate: actions.startRemoveCountrysideRouteTemplate,
      onStartRenameRouteGroup: actions.startRenameCountrysideRouteGroup,
      onUpdateRouteGroupForm: actions.updateCountrysideRouteGroupForm,
      onUpdateRouteTemplateForm: actions.updateCountrysideRouteTemplateForm,
    }),
  );
  return wrapper;
}


function createOpShopTripSummary(board, collections, state, actions) {
  if (!board) {
    return createEmptyState("No OP SHOP workspace data loaded.", "store");
  }
  const pickupDate = state.opshopTripSummaryDate || state.dispatchDate;
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-opshop-trip-summary";
  wrapper.append(createOpShopTripSummaryToolbar(pickupDate, state, actions));
  const assignedForDate = (board.opshop_pickups || []).filter(
    (pickup) => pickup.pickup_date === pickupDate && currentDriverId(pickup),
  );
  wrapper.append(
    createMetricGrid([
      ["Pickup date", pickupDate, "calendar"],
      ["Assigned pickups", assignedForDate.length, "store"],
      ["Drivers", (board.drivers || []).length, "user"],
    ]),
  );
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-driver-grid workspace-opshop-driver-grid";
  if (!(board.drivers || []).length) {
    grid.append(createEmptyState("No drivers are available for OP SHOP Trip Summary.", "user"));
  } else {
    (board.drivers || []).forEach((driver) => {
      grid.append(createOpShopDriverSummaryCard(
        driver,
        board,
        collections,
        pickupDate,
        state,
        actions,
      ));
    });
  }
  wrapper.append(grid);
  return wrapper;
}


function createOpShopTripSummaryToolbar(pickupDate, state, actions) {
  const panel = document.createElement("section");
  panel.className = "workspace-context-panel workspace-context-panel-opshop workspace-opshop-trip-toolbar";
  const heading = createSectionHeading(
    "OP SHOP Trip Summary",
    "Review assigned pickups by driver before generating a Pickup Collection.",
  );
  const field = document.createElement("label");
  field.className = "workspace-date-control workspace-opshop-pickup-date-control";
  field.textContent = "Pickup date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = pickupDate;
  input.disabled = state.isOpShopWorkspaceLoading;
  input.addEventListener("change", () => actions.updateOpShopTripSummaryDate(input.value));
  field.append(input);
  panel.append(heading, field);
  return panel;
}


function createOpShopDriverSummaryCard(
  driver,
  board,
  collections,
  pickupDate,
  state,
  actions,
) {
  const card = document.createElement("article");
  card.className = "workspace-record-card workspace-driver-card workspace-opshop-driver-card";
  const pickups = assignedOpShopPickupsForDriver(board, pickupDate, driver.driver_id);
  const collection = findPickupCollectionForDriver(collections, pickupDate, driver.driver_id);
  const isLocked = Boolean(collection && ["GENERATED", "SAVED"].includes(collection.status));
  const candidates = readyPickupCollectionCandidates(board, collections);
  const candidate = candidates.find(
    (item) => item.pickup_date === pickupDate && item.driver_id === driver.driver_id,
  );

  const top = document.createElement("div");
  top.className = "workspace-record-card-top";
  const identity = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = formatOptional(driver.name, driver.driver_id);
  const badges = document.createElement("div");
  badges.className = "workspace-inline-badges";
  badges.append(createBadge(driver.is_available === false ? "Unavailable" : "Available"));
  if (collection) {
    badges.append(createBadge(collection.status));
  }
  identity.append(heading, badges);
  top.append(identity);

  const counts = pickupCategoryCounts(pickups);
  const facts = document.createElement("dl");
  facts.className = "workspace-fact-grid";
  appendFact(facts, "Regular pickups", counts.regular);
  appendFact(facts, "Oncall pickups", counts.oncall);
  appendFact(facts, "Countryside pickups", counts.countryside);
  appendFact(facts, "Total pickups", pickups.length);
  card.append(top, facts);

  if (isLocked) {
    card.append(createStatus(
      collection.status === "SAVED"
        ? "Saved Pickup Collection locks this driver and pickup date."
        : "Generated Pickup Collection is awaiting confirmation on the Pickup Collections page.",
      "loading",
    ));
  }

  card.append(
    createOpShopPickupGroup("Regular", pickups.filter(isRegularPickup), isLocked, state, actions),
    createOpShopPickupGroup("Oncall", pickups.filter(isOncallPickup), isLocked, state, actions),
    createOpShopPickupGroup("Countryside", pickups.filter(isCountrysidePickup), isLocked, state, actions),
  );

  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  if (candidate && !isLocked) {
    actionsRow.append(createActionButton(
      "Generate Pickup Collection",
      () => actions.generateOpShopPickupCollection(candidate),
      {
        disabled: isBusy(state, `opshop-generate:${pickupDate}:${driver.driver_id}`),
        primary: true,
      },
    ));
  }
  card.append(actionsRow);
  return card;
}


function createOpShopPickupGroup(titleText, pickups, isLocked, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-trip-panel workspace-opshop-trip-group";
  const title = document.createElement("h4");
  title.textContent = `${titleText} (${pickups.length})`;
  section.append(title);
  if (!pickups.length) {
    section.append(createEmptyState(`No ${titleText} pickups assigned`, "store"));
    return section;
  }
  pickups.forEach((pickup) => {
    section.append(createOpShopTripPickupRow(pickup, isLocked, state, actions));
  });
  return section;
}


function createOpShopTripPickupRow(pickup, isLocked, state, actions) {
  const row = document.createElement("article");
  row.className = "workspace-record-card workspace-opshop-trip-pickup-row";
  const copy = document.createElement("div");
  const heading = document.createElement("h5");
  heading.textContent = formatOptional(pickup.opshop_name);
  const meta = document.createElement("p");
  meta.textContent = [
    formatOptional(pickup.suburb),
    pickupCategoryLabel(pickup),
    isCountrysidePickup(pickup) ? pickup.route_group_name : "",
  ].filter(Boolean).join(" - ");
  copy.append(heading, meta);
  const notes = joinValues(pickup.task_notes, pickup.status_notes, pickup.access_type);
  if (notes !== "-") {
    const detail = document.createElement("p");
    detail.className = "workspace-muted workspace-opshop-trip-notes";
    detail.textContent = notes;
    copy.append(detail);
  }
  const button = createActionButton(
    "Unassign",
    () => actions.unassignOpShopPickup(pickup.pickup_task_id),
    {
      disabled:
        isLocked
        || pickup.assigned_to_locked
        || isBusy(state, `opshop-unassign:${pickup.pickup_task_id}`),
    },
  );
  row.append(copy, button);
  return row;
}


function createCollectionList(collections, state, actions) {
  const generated = (collections || []).filter((collection) => collection.status === "GENERATED");
  const saved = (collections || []).filter((collection) => collection.status === "SAVED");
  const wrapper = document.createElement("div");
  wrapper.className = "workspace-stack workspace-pickup-collections";
  wrapper.append(
    createCollectionSection(
      "Generated Pickup Collections",
      "Awaiting confirmation. Save to lock the snapshot, or cancel to restore editable pickups.",
      generated,
      "No generated Pickup Collections are awaiting confirmation.",
      state,
      actions,
    ),
    createCollectionSection(
      "Saved Pickup Collections",
      "Saved collection history remains available here for review and export.",
      saved,
      "No saved Pickup Collections for this dispatch date.",
      state,
      actions,
    ),
  );
  return wrapper;
}


function createCollectionSection(titleText, description, collections, emptyMessage, state, actions) {
  const section = document.createElement("section");
  section.className = "workspace-context-panel workspace-context-panel-opshop workspace-collection-section";
  section.append(createSectionHeading(titleText, description));
  const grid = document.createElement("div");
  grid.className = "workspace-card-grid workspace-collection-grid";
  if (!collections.length) {
    grid.append(createEmptyState(emptyMessage, "history"));
  } else {
    collections.forEach((collection) => grid.append(createCollectionCard(collection, state, actions)));
  }
  section.append(grid);
  return section;
}


function createCollectionCard(collection, state, actions) {
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
  const counts = pickupCategoryCounts(collection.pickups || []);
  appendFact(facts, "Pickup count", (collection.pickups || []).length);
  appendFact(facts, "Regular pickups", counts.regular);
  appendFact(facts, "Oncall pickups", counts.oncall);
  appendFact(facts, "Countryside pickups", counts.countryside);
  appendFact(facts, "Generated", collection.generated_at);
  appendFact(facts, "Saved", collection.saved_at || "Not saved");
  appendFact(facts, "Saved by", collection.saved_by_account_name || "Not saved");
  const actionsRow = document.createElement("div");
  actionsRow.className = "workspace-action-row";
  if (collection.status === "GENERATED") {
    actionsRow.append(
      createActionButton(
        "Save",
        () => actions.saveOpShopPickupCollection(collection.collection_id),
        {
          disabled: isBusy(state, `opshop-save:${collection.collection_id}`),
          primary: true,
        },
      ),
      createActionButton(
        "Cancel",
        () => actions.cancelOpShopPickupCollection(collection.collection_id),
        { disabled: isBusy(state, `opshop-cancel:${collection.collection_id}`) },
      ),
    );
  }
  if (collection.status === "SAVED") {
    actionsRow.append(
      createActionButton(
        "Export",
        () => actions.exportOpShopPickupCollection(collection.collection_id),
        {
          disabled: isBusy(state, `opshop-export:${collection.collection_id}`),
          primary: true,
        },
      ),
    );
  }
  card.append(top, facts, actionsRow);
  return card;
}


function readyPickupCollectionCandidates(board, collections) {
  const reservedKeys = new Set(
    (collections || [])
      .filter((collection) => ["GENERATED", "SAVED"].includes(collection.status))
      .map((collection) => `${collection.pickup_date}|${collection.driver_id}`),
  );
  const groups = new Map();
  (board.opshop_pickups || []).forEach((pickup) => {
    const driverId = currentDriverId(pickup);
    if (!driverId || !pickup.pickup_date) {
      return;
    }
    const key = `${pickup.pickup_date}|${driverId}`;
    if (reservedKeys.has(key)) {
      return;
    }
    if (!groups.has(key)) {
      groups.set(key, {
        pickup_date: pickup.pickup_date,
        driver_id: driverId,
        pickups: [],
        regular_count: 0,
        oncall_count: 0,
        countryside_count: 0,
      });
    }
    const group = groups.get(key);
    group.pickups.push(pickup);
    if (pickup.pickup_category === "COUNTRYSIDE") {
      group.countryside_count += 1;
    } else if (pickup.run_type === "REGULAR") {
      group.regular_count += 1;
    } else if (pickup.run_type === "ON_CALL") {
      group.oncall_count += 1;
    }
  });
  return Array.from(groups.values()).sort((left, right) =>
    `${left.pickup_date}|${left.driver_id}`.localeCompare(`${right.pickup_date}|${right.driver_id}`),
  );
}


function assignedOpShopPickupsForDriver(board, pickupDate, driverId) {
  return (board.opshop_pickups || []).filter(
    (pickup) =>
      pickup.pickup_date === pickupDate
      && currentDriverId(pickup) === driverId,
  );
}


function findPickupCollectionForDriver(collections, pickupDate, driverId) {
  return (collections || []).find(
    (collection) =>
      collection.pickup_date === pickupDate
      && collection.driver_id === driverId
      && ["GENERATED", "SAVED"].includes(collection.status),
  );
}


function pickupCategoryCounts(pickups) {
  return (pickups || []).reduce(
    (counts, pickup) => {
      if (isCountrysidePickup(pickup)) {
        counts.countryside += 1;
      } else if (isRegularPickup(pickup)) {
        counts.regular += 1;
      } else {
        counts.oncall += 1;
      }
      return counts;
    },
    { regular: 0, oncall: 0, countryside: 0 },
  );
}


function isCountrysidePickup(pickup) {
  return (pickup.pickup_category || pickup.pickup_category_snapshot) === "COUNTRYSIDE";
}


function isRegularPickup(pickup) {
  return !isCountrysidePickup(pickup)
    && (pickup.run_type || pickup.run_type_snapshot) === "REGULAR";
}


function isOncallPickup(pickup) {
  return !isCountrysidePickup(pickup)
    && (pickup.run_type || pickup.run_type_snapshot) === "ON_CALL";
}


function pickupCategoryLabel(pickup) {
  if (isCountrysidePickup(pickup)) {
    return "Countryside";
  }
  return isRegularPickup(pickup) ? "Regular" : "Oncall";
}


function changedOpShopAssignments(pickups, state) {
  return (pickups || []).filter((pickup) => {
    if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, pickup.pickup_task_id)) {
      return false;
    }
    return state.opshopAssignmentDrafts[pickup.pickup_task_id] !== currentDriverId(pickup);
  });
}


function selectedOpShopDriverId(pickup, state) {
  if (Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, pickup.pickup_task_id)) {
    return state.opshopAssignmentDrafts[pickup.pickup_task_id];
  }
  return currentDriverId(pickup);
}


function currentDriverId(pickup) {
  return pickup?.assigned_driver_id || pickup?.driver_id || "";
}


function defaultDriverHint(pickup, state) {
  if (pickup.run_type !== "REGULAR" || pickup.pickup_category === "COUNTRYSIDE") {
    return "None";
  }
  const defaultName = pickup.default_driver_name || pickup.default_driver_alias || "";
  if (!defaultName) {
    return "None";
  }
  if (currentDriverId(pickup) || !pickup.pickup_date || pickup.pickup_date < state.dispatchDate) {
    return "None";
  }
  const defaultDriverExists = (state.opshopBoard?.drivers || []).some(
    (driver) => driver.driver_id === pickup.default_driver_id,
  );
  if (pickup.default_driver_id && defaultDriverExists) {
    return `${defaultName} suggested`;
  }
  return `${defaultName} unavailable`;
}


function templatesByRouteGroup(board) {
  const groups = new Map();
  (board.templates || [])
    .filter((template) => template.pickup_category === "COUNTRYSIDE" && template.route_group_id)
    .forEach((template) => {
      if (!groups.has(template.route_group_id)) {
        groups.set(template.route_group_id, []);
      }
      groups.get(template.route_group_id).push(template);
    });
  return groups;
}


function createSelect(labelText, value, options, onChange) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const select = document.createElement("select");
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  });
  select.value = value || "";
  select.addEventListener("change", () => onChange(select.value));
  label.append(text, select);
  return label;
}


function createDateField(labelText, value, onChange) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("input");
  input.type = "date";
  input.value = value || "";
  input.addEventListener("change", () => onChange(input.value));
  label.append(text, input);
  return label;
}


function createTextField(labelText, value, onChange) {
  const label = document.createElement("label");
  label.className = "workspace-field";
  const text = document.createElement("span");
  text.textContent = labelText;
  const input = document.createElement("input");
  input.type = "text";
  input.value = value || "";
  input.addEventListener("input", () => onChange(input.value));
  label.append(text, input);
  return label;
}


function createActionButton(label, onClick, { disabled = false, primary = false } = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = primary ? "button-primary workspace-action-button" : "button-secondary workspace-action-button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", onClick);
  return button;
}


function createRouteActionLink(label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.className = "button-secondary workspace-action-button workspace-route-action-link";
  link.textContent = label;
  return link;
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
  return values.filter(Boolean).join(" - ") || "-";
}


function isBusy(state, actionKey) {
  return Boolean(state.opshopBusyActionKeys?.[actionKey]);
}
