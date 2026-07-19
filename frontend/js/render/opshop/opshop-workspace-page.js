import { createIcon } from "../../utils/icon-utils.js";

const OPSHOP_TABS = [
  { route: "opshop/task-pool/regular", label: "Task Pool" },
  { route: "opshop/trip-summary", label: "Trip Summary" },
  { route: "opshop/collections", label: "Pickup Collections" },
  { route: "opshop/history", label: "Saved History" },
];

export function createWorkspacePage(state, onDispatchDateChange) {
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
  heading.append(titleGroup);
  if (state.workspaceRoute.startsWith("opshop/task-pool/")) {
    heading.append(createDateControl(state, onDispatchDateChange));
  }

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

export function createDateControl(state, onDispatchDateChange) {
  const label = document.createElement("label");
  label.className = "workspace-date-control";
  label.textContent = "Pickup workspace date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = state.dispatchDate;
  input.disabled = state.isOpShopWorkspaceLoading;
  input.addEventListener("change", () => onDispatchDateChange(input.value));
  label.append(input);
  return label;
}

export function createTab(tab, activeRoute) {
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
