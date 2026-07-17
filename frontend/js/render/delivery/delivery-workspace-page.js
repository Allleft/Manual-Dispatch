import { createIcon } from "../../utils/icon-utils.js";

const DELIVERY_TABS = [
  { route: "delivery/task-pool", label: "Task Pool" },
  { route: "delivery/trip-summary", label: "Trip Summary" },
  { route: "delivery/run-sheet", label: "Run Sheets" },
  { route: "delivery/history", label: "Saved History" },
];

export function createWorkspacePage(state, onDispatchDateChange) {
  const page = document.createElement("section");
  page.className = "workspace-page workspace-page-delivery";

  const heading = document.createElement("header");
  heading.className = "workspace-page-heading";
  const titleGroup = document.createElement("div");
  titleGroup.className = "workspace-page-title-group";
  const icon = document.createElement("span");
  icon.className = "workspace-page-icon";
  icon.append(createIcon("truck"));
  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Delivery workspace";
  const title = document.createElement("h2");
  title.textContent = "Order Delivery";
  const description = document.createElement("p");
  description.textContent = "Plan driver trips, generate Delivery Run Sheets, and review saved history.";
  copy.append(kicker, title, description);
  titleGroup.append(icon, copy);
  heading.append(titleGroup);
  if (state.workspaceRoute === "delivery/task-pool") {
    heading.append(createDateControl(state, onDispatchDateChange));
  }

  const nav = document.createElement("nav");
  nav.className = "workspace-tabs workspace-tabs-delivery";
  nav.setAttribute("aria-label", "Order Delivery workspace");
  DELIVERY_TABS.forEach((tab) => nav.append(createTab(tab, state.workspaceRoute)));

  page.append(heading, nav);
  return page;
}

export function createDateControl(state, onDispatchDateChange) {
  const label = document.createElement("label");
  label.className = "workspace-date-control";
  label.textContent = "Dispatch board date";
  const input = document.createElement("input");
  input.type = "date";
  input.value = state.dispatchDate;
  input.disabled = state.isDeliveryWorkspaceLoading;
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
