import { createIcon } from "../utils/icon-utils.js";


const WORKSPACES = [
  {
    className: "delivery",
    href: "#delivery/task-pool",
    icon: "truck",
    kicker: "Delivery operations",
    title: "Order Delivery",
    description:
      "Manage delivery orders, assign drivers and vehicles, prepare Delivery Run Sheets, and review saved history.",
    action: "Open Order Delivery",
    readyField: "delivery_ready",
  },
  {
    className: "opshop",
    href: "#opshop/task-pool",
    icon: "store",
    kicker: "Pickup operations",
    title: "OP SHOP Pickup",
    description:
      "Manage regular, oncall and countryside pickups, prepare Pickup Collections, and review saved history.",
    action: "Open OP SHOP Pickup",
    readyField: "opshop_ready",
  },
];


export function renderWorkspaceHome(root, { state }) {
  root.innerHTML = "";

  const intro = document.createElement("section");
  intro.className = "workspace-home-intro";
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Choose a workspace";
  const title = document.createElement("h2");
  title.textContent = "Where are you working today?";
  const copy = document.createElement("p");
  copy.textContent =
    "Delivery orders and OP SHOP pickups now have separate workspaces, records, and saved operational history.";
  intro.append(kicker, title, copy);

  const grid = document.createElement("section");
  grid.className = "workspace-home-grid";
  grid.setAttribute("aria-label", "Available workspaces");
  WORKSPACES.forEach((workspace) =>
    grid.append(createWorkspaceCard(workspace, state)),
  );

  root.append(intro, createMigrationNotice(state), grid);
}


function createWorkspaceCard(workspace, state) {
  const status = state.workspaceMigrationStatus;
  const isDisabled =
    state.isWorkspaceMigrationStatusLoading ||
    Boolean(state.workspaceMigrationStatusError) ||
    !status ||
    !status[workspace.readyField];
  const card = document.createElement(isDisabled ? "article" : "a");
  if (!isDisabled) {
    card.href = workspace.href;
  } else {
    card.setAttribute("aria-disabled", "true");
  }
  card.className = `workspace-home-card workspace-home-card-${workspace.className}`;
  card.classList.toggle("workspace-home-card-disabled", isDisabled);

  const icon = document.createElement("span");
  icon.className = "workspace-home-card-icon";
  icon.append(createIcon(workspace.icon));

  const content = document.createElement("span");
  content.className = "workspace-home-card-content";
  const kicker = document.createElement("span");
  kicker.className = "workspace-home-card-kicker";
  kicker.textContent = workspace.kicker;
  const title = document.createElement("strong");
  title.textContent = workspace.title;
  const description = document.createElement("span");
  description.className = "workspace-home-card-description";
  description.textContent = workspace.description;
  content.append(kicker, title, description);

  const action = document.createElement("span");
  action.className = "workspace-home-card-action";
  const actionLabel = isDisabled
    ? state.isWorkspaceMigrationStatusLoading
      ? "Checking readiness"
      : "Migration required"
    : workspace.action;
  action.append(document.createTextNode(actionLabel), createIcon("arrow-right"));

  card.append(icon, content, action);
  return card;
}


function createMigrationNotice(state) {
  const notice = document.createElement("section");
  notice.className = "workspace-migration-notice";
  notice.setAttribute("role", "status");

  if (state.isWorkspaceMigrationStatusLoading) {
    notice.classList.add("workspace-migration-notice-checking");
    notice.textContent = "Checking workspace migration readiness...";
    return notice;
  }
  if (state.workspaceMigrationStatusError) {
    notice.classList.add("workspace-migration-notice-blocked");
    notice.textContent = state.workspaceMigrationStatusError;
    return notice;
  }

  const status = state.workspaceMigrationStatus;
  if (!status || (status.delivery_ready && status.opshop_ready)) {
    notice.hidden = true;
    return notice;
  }

  notice.classList.add("workspace-migration-notice-blocked");
  if (status.legacy_generated_summary_count) {
    notice.textContent =
      `${status.legacy_generated_summary_count} generated legacy Final Trip ` +
      "Summary record(s) must be resolved before either workspace can open.";
    return notice;
  }

  const blocked = [];
  if (!status.delivery_ready) {
    blocked.push(
      `Order Delivery (${status.delivery_unmigrated_summary_count} legacy summary record(s))`,
    );
  }
  if (!status.opshop_ready) {
    blocked.push(
      `OP SHOP Pickup (${status.opshop_unmigrated_summary_count} legacy summary record(s))`,
    );
  }
  notice.textContent =
    `Workspace migration is required for ${blocked.join(" and ")}. ` +
    "Run the legacy snapshot migration during a maintenance window.";
  return notice;
}
