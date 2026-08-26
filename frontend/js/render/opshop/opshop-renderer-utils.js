import { createIcon } from "../../utils/icon-utils.js";

import { formatOptional } from "../../utils/format-utils.js";

export function compareText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, {
    sensitivity: "base",
  });
}

export function compareRegularRouteSequence(left, right) {
  const leftSequence = positiveRouteSequence(left.regular_route_sequence);
  const rightSequence = positiveRouteSequence(right.regular_route_sequence);
  if (leftSequence !== null && rightSequence === null) {
    return -1;
  }
  if (leftSequence === null && rightSequence !== null) {
    return 1;
  }
  if (leftSequence !== null && rightSequence !== null && leftSequence !== rightSequence) {
    return leftSequence - rightSequence;
  }
  return compareText(left.suburb, right.suburb)
    || compareText(left.opshop_name, right.opshop_name)
    || compareText(left.pickup_task_id, right.pickup_task_id);
}

export function compareCountrysideTripSequence(left, right) {
  const leftSequence = positiveRouteSequence(left.trip_sequence);
  const rightSequence = positiveRouteSequence(right.trip_sequence);
  if (leftSequence !== null && rightSequence === null) {
    return -1;
  }
  if (leftSequence === null && rightSequence !== null) {
    return 1;
  }
  if (leftSequence !== null && rightSequence !== null && leftSequence !== rightSequence) {
    return leftSequence - rightSequence;
  }
  return compareText(left.route_group_name, right.route_group_name)
    || compareText(left.suburb, right.suburb)
    || compareText(left.opshop_name, right.opshop_name)
    || compareText(left.pickup_task_id, right.pickup_task_id);
}

export function readyPickupCollectionCandidates(board, collections) {
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

export function assignedOpShopPickupsForDriver(board, pickupDate, driverId) {
  return (board.opshop_pickups || []).filter(
    (pickup) =>
      pickup.pickup_date === pickupDate
      && currentDriverId(pickup) === driverId,
  );
}

export function findPickupCollectionForDriver(collections, pickupDate, driverId) {
  return (collections || []).find(
    (collection) =>
      collection.pickup_date === pickupDate
      && collection.driver_id === driverId
      && ["GENERATED", "SAVED"].includes(collection.status),
  );
}

export function pickupCategoryCounts(pickups) {
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

export function isCountrysidePickup(pickup) {
  return (pickup.pickup_category || pickup.pickup_category_snapshot) === "COUNTRYSIDE";
}

export function isRegularPickup(pickup) {
  return !isCountrysidePickup(pickup)
    && (pickup.run_type || pickup.run_type_snapshot) === "REGULAR";
}

export function isOncallPickup(pickup) {
  return !isCountrysidePickup(pickup)
    && (pickup.run_type || pickup.run_type_snapshot) === "ON_CALL";
}

export function pickupCategoryLabel(pickup) {
  if (isCountrysidePickup(pickup)) {
    return "Countryside";
  }
  return isRegularPickup(pickup) ? "Regular" : "Oncall";
}

export function changedOpShopAssignments(pickups, state) {
  return (pickups || []).filter((pickup) => {
    if (pickup.assigned_to_locked) {
      return false;
    }
    if (!Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, pickup.pickup_task_id)) {
      return false;
    }
    return state.opshopAssignmentDrafts[pickup.pickup_task_id] !== currentDriverId(pickup);
  });
}

export function selectedOpShopDriverId(pickup, state) {
  if (Object.prototype.hasOwnProperty.call(state.opshopAssignmentDrafts, pickup.pickup_task_id)) {
    return state.opshopAssignmentDrafts[pickup.pickup_task_id];
  }
  return currentDriverId(pickup);
}

export function effectiveRegularRouteDriverName(pickup, state) {
  const hasDraft = Object.prototype.hasOwnProperty.call(
    state.opshopAssignmentDrafts || {},
    pickup.pickup_task_id,
  );
  const draftDriverId = hasDraft
    ? state.opshopAssignmentDrafts[pickup.pickup_task_id]
    : "";
  const driverId = draftDriverId || (!hasDraft ? currentDriverId(pickup) : "")
    || pickup.default_driver_id
    || "";
  const driver = (state.opshopBoard?.drivers || []).find(
    (item) => item.driver_id === driverId,
  );
  return driver?.name
    || driverId
    || pickup.default_driver_name
    || pickup.default_driver_alias
    || "";
}

export function currentDriverId(pickup) {
  return pickup?.assigned_driver_id || pickup?.driver_id || "";
}

function positiveRouteSequence(value) {
  const sequence = Number(value);
  return Number.isInteger(sequence) && sequence > 0 ? sequence : null;
}

export function defaultDriverHint(pickup, state) {
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

export function createSelect(labelText, value, options, onChange) {
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

export function createDateField(labelText, value, onChange) {
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

export function createTextField(labelText, value, onChange) {
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

export function createActionButton(label, onClick, { disabled = false, primary = false } = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = primary ? "button-primary workspace-action-button" : "button-secondary workspace-action-button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", onClick);
  return button;
}

export function createRouteActionLink(label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.className = "button-secondary workspace-action-button workspace-route-action-link";
  link.textContent = label;
  return link;
}

export function createMetricGrid(metrics) {
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

export function createSectionHeading(titleText, descriptionText = "") {
  const heading = document.createElement("div");
  heading.className = "workspace-section-heading";
  const title = document.createElement("h3");
  title.textContent = titleText;
  heading.append(title);
  if (descriptionText) {
    const description = document.createElement("p");
    description.textContent = descriptionText;
    heading.append(description);
  }
  return heading;
}

export function appendFact(list, labelText, value) {
  const item = document.createElement("div");
  const label = document.createElement("dt");
  label.textContent = labelText;
  const detail = document.createElement("dd");
  detail.textContent = formatOptional(value);
  item.append(label, detail);
  list.append(item);
}

export function createBadge(label) {
  const badge = document.createElement("span");
  badge.className = "workspace-badge";
  badge.textContent = label;
  return badge;
}

export function createStatus(message, type) {
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

export function createEmptyState(message, iconName) {
  const empty = document.createElement("div");
  empty.className = "workspace-empty-state";
  empty.append(createIcon(iconName));
  const text = document.createElement("p");
  text.textContent = message;
  empty.append(text);
  return empty;
}

export function joinValues(...values) {
  return values.filter(Boolean).join(" - ") || "-";
}

export function isBusy(state, actionKey) {
  return Boolean(state.opshopBusyActionKeys?.[actionKey]);
}
