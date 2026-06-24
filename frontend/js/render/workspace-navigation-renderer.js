import { createIcon } from "../utils/icon-utils.js";


export function renderWorkspaceNavigation({ state }) {
  const nav = document.querySelector("#workspace-header-nav");
  if (!nav) {
    return;
  }
  nav.innerHTML = "";
  nav.hidden = !state.isLoggedIn;
  if (!state.isLoggedIn) {
    return;
  }

  nav.append(
    createNavigationLink("#home", "Home", "home", state.workspaceRoute === "home"),
    createNavigationLink("#home", "Switch workspace", "refresh", false),
  );

  if (state.activeWorkspace) {
    const label = state.activeWorkspace === "delivery" ? "Order Delivery" : "OP SHOP Pickup";
    const context = document.createElement("span");
    context.className = `workspace-context-badge workspace-context-${state.activeWorkspace}`;
    context.textContent = label;
    nav.append(context);
  }
}


function createNavigationLink(href, label, iconName, isCurrent) {
  const link = document.createElement("a");
  link.href = href;
  link.className = "workspace-header-link";
  link.append(createIcon(iconName), document.createTextNode(label));
  if (isCurrent) {
    link.classList.add("workspace-header-link-active");
    link.setAttribute("aria-current", "page");
  }
  return link;
}
