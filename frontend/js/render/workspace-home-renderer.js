import { createIcon } from "../utils/icon-utils.js";


const WORKSPACES = [
  {
    className: "delivery",
    href: "#delivery/task-pool",
    icon: "truck",
    title: "Order Delivery",
    action: "Open Order Delivery",
    readyField: "delivery_ready",
  },
  {
    className: "opshop",
    href: "#opshop/task-pool/regular",
    icon: "store",
    title: "OP SHOP Pickup",
    action: "Open OP SHOP Pickup",
    readyField: "opshop_ready",
  },
];


export function renderWorkspaceHome(root, { state }) {
  root.innerHTML = "";

  const intro = document.createElement("section");
  intro.className = "workspace-home-intro";
  const title = document.createElement("h2");
  title.textContent = "Where are you working today?";
  intro.append(title);

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
  const title = document.createElement("strong");
  title.textContent = workspace.title;
  content.append(title);

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
