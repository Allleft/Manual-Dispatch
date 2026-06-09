const BOARD_VIEW_TABS = [
  { id: "task-pool", label: "Task Pool" },
  { id: "trip-summary", label: "Trip Summary" },
  { id: "final-summary", label: "Final Trip Summary" },
];

export function renderBoardViewNavigation({ activeView, onSelectView }) {
  const nav = document.querySelector("#board-view-nav");
  if (!nav) {
    return;
  }

  nav.innerHTML = "";
  BOARD_VIEW_TABS.forEach((tab) => {
    const button = document.createElement("button");
    const isActive = tab.id === activeView;

    button.type = "button";
    button.className = isActive ? "board-view-tab board-view-tab-active" : "board-view-tab";
    button.textContent = tab.label;
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
    if (isActive) {
      button.setAttribute("aria-current", "page");
    }
    button.addEventListener("click", () => onSelectView(tab.id));

    nav.append(button);
  });
}
