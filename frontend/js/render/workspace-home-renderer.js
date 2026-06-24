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
  },
  {
    className: "opshop",
    href: "#opshop/regular",
    icon: "store",
    kicker: "Pickup operations",
    title: "OP SHOP Pickup",
    description:
      "Manage regular, oncall and countryside pickups, prepare Pickup Collections, and review saved history.",
    action: "Open OP SHOP Pickup",
  },
];


export function renderWorkspaceHome(root) {
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
  WORKSPACES.forEach((workspace) => grid.append(createWorkspaceCard(workspace)));

  root.append(intro, grid);
}


function createWorkspaceCard(workspace) {
  const card = document.createElement("a");
  card.href = workspace.href;
  card.className = `workspace-home-card workspace-home-card-${workspace.className}`;

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
  action.append(document.createTextNode(workspace.action), createIcon("arrow-right"));

  card.append(icon, content, action);
  return card;
}
