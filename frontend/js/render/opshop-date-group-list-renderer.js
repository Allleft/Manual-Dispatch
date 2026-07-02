import { createIcon } from "../utils/icon-utils.js";
import {
  getDateGroupCollapsed,
  getDateGroupListId,
} from "../utils/opshop-date-group-utils.js";


export function createOpShopDateGroupList({
  collapsedDates,
  comparePickups = null,
  dispatchDate,
  emptyMessage,
  idPrefix,
  loading = false,
  loadingMessage = "Loading OP SHOP pickups...",
  onToggleDateGroup,
  pickups,
  renderPickup,
}) {
  const container = document.createElement("div");
  container.className = "opshop-date-group-list";

  if (loading && pickups.length === 0) {
    container.append(createMessage(loadingMessage));
    return container;
  }
  if (pickups.length === 0) {
    container.append(createMessage(emptyMessage));
    return container;
  }

  groupOpShopPickupsByDate(pickups, comparePickups).forEach(
    ([pickupDate, datePickups]) => {
      const section = document.createElement("section");
      section.className = "opshop-date-group";
      const collapsed = getDateGroupCollapsed(
        collapsedDates,
        pickupDate,
        dispatchDate,
      );
      const listId = getDateGroupListId(idPrefix, pickupDate);
      const heading = document.createElement("h3");
      heading.className = "opshop-date-group-heading";
      heading.append(
        createDateGroupToggle({
          collapsed,
          listId,
          onToggleDateGroup,
          pickupCount: datePickups.length,
          pickupDate,
        }),
      );

      const list = document.createElement("div");
      list.className = "opshop-date-card-list";
      list.id = listId;
      list.hidden = collapsed;
      datePickups.forEach((pickup) => list.append(renderPickup(pickup)));
      section.append(heading, list);
      container.append(section);
    },
  );
  return container;
}


export function groupOpShopPickupsByDate(pickups, comparePickups = null) {
  const groups = new Map();
  [...pickups]
    .sort((left, right) => compareText(left.pickup_date, right.pickup_date))
    .forEach((pickup) => {
      const key = pickup.pickup_date || "";
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key).push(pickup);
    });
  return [...groups.entries()].map(([pickupDate, datePickups]) => [
    pickupDate,
    comparePickups ? [...datePickups].sort(comparePickups) : datePickups,
  ]);
}


function createDateGroupToggle({
  collapsed,
  listId,
  onToggleDateGroup,
  pickupCount,
  pickupDate,
}) {
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "opshop-date-group-toggle";
  toggle.setAttribute("aria-controls", listId);
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    onToggleDateGroup(pickupDate);
  });

  const label = document.createElement("span");
  label.className = "opshop-date-group-label";
  label.append(
    createIcon("calendar"),
    document.createTextNode(formatDateHeading(pickupDate)),
  );
  const count = document.createElement("span");
  count.className = "opshop-date-group-count";
  count.textContent = `(${pickupCount} ${pickupCount === 1 ? "pickup" : "pickups"})`;
  const stateLabel = document.createElement("span");
  stateLabel.className = "opshop-date-group-state";
  stateLabel.append(
    document.createTextNode(collapsed ? "Collapsed" : "Expanded"),
    createIcon(collapsed ? "chevron-down" : "chevron-up"),
  );
  const title = document.createElement("span");
  title.className = "opshop-date-group-title";
  title.append(label, count);
  toggle.append(title, stateLabel);
  return toggle;
}


function createMessage(message) {
  const element = document.createElement("p");
  element.className = "empty-board";
  element.textContent = message;
  return element;
}


function formatDateHeading(value) {
  const date = parseLocalDate(value);
  if (!date) {
    return value || "-";
  }
  return `${WEEKDAYS[date.getDay()]} ${date.getDate()}/${date.getMonth() + 1}`;
}


function parseLocalDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) {
    return null;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}


function compareText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, {
    sensitivity: "base",
  });
}


const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];
