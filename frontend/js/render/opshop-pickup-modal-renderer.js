import { getOpShopPickupByTaskId } from "../state/selectors.js";
import { state } from "../state/app-state.js";
import {
  createDetailField,
  createModalKicker,
  setButtonContent,
} from "../utils/dom-utils.js";
import { formatOptional } from "../utils/format-utils.js";

export function renderOpShopPickupDetailPopup({ onCloseOpShopPickupDetail }) {
  let root = document.querySelector("#opshop-pickup-detail-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "opshop-pickup-detail-root";
    document.body.append(root);
  }

  clearEscapeHandler(root);
  root.innerHTML = "";
  if (!state.activeOpShopPickupDetailId) {
    return;
  }

  const pickup = getOpShopPickupByTaskId(state.activeOpShopPickupDetailId);
  if (!pickup) {
    state.activeOpShopPickupDetailId = "";
    return;
  }

  const backdrop = document.createElement("div");
  backdrop.className = "detail-backdrop";
  backdrop.addEventListener("click", onCloseOpShopPickupDetail);

  const modal = document.createElement("article");
  modal.className = "order-detail-modal opshop-detail-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-labelledby", "opshop-pickup-detail-title");
  modal.addEventListener("click", (event) => event.stopPropagation());
  root.opshopEscapeHandler = (event) => {
    if (event.key === "Escape") {
      onCloseOpShopPickupDetail();
    }
  };
  document.addEventListener("keydown", root.opshopEscapeHandler);

  const header = document.createElement("div");
  header.className = "detail-header";

  const titleWrap = document.createElement("div");
  const kicker = createModalKicker("OP SHOP PICKUP", "bag");

  const title = document.createElement("h2");
  title.id = "opshop-pickup-detail-title";
  title.textContent = `${formatOptional(pickup.opshop_name)} - ${formatOptional(pickup.suburb)}`;

  titleWrap.append(kicker, title);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button-secondary detail-close";
  setButtonContent(closeButton, "Close", "x", { iconAfter: true });
  closeButton.addEventListener("click", onCloseOpShopPickupDetail);

  header.append(titleWrap, closeButton);

  modal.append(
    header,
    createDetailSection("General", [
      ["Op Shop Name", pickup.opshop_name],
      ["Pickup Date", pickup.pickup_date],
      ["Run Day", pickup.run_day],
      ["Run Type", pickup.run_type],
      ["Pickup Frequency", pickup.pickup_frequency],
      ["Generated From", pickup.generated_from],
      ["Status", pickup.status],
      ["Area / Region", pickup.area_region],
    ]),
    createDetailSection("Address / Access", [
      ["Street Address", pickup.street_address],
      ["Suburb", pickup.suburb],
      ["Access Type", pickup.access_type],
      ["Key Required", formatBoolean(pickup.key_required)],
      ["Trailer Restriction", pickup.trailer_restriction],
    ]),
    createDetailSection("Contact", [
      ["Primary Contact", pickup.primary_contact],
      ["Primary Phone", pickup.primary_phone],
      ["Secondary Contact", pickup.secondary_contact],
      ["Secondary Phone", pickup.secondary_phone],
      ["Call Before Arrival", formatBoolean(pickup.call_before_arrival)],
      ["Call Timing", pickup.call_timing],
    ]),
    createDetailSection("Notes", [
      ["Status Notes", pickup.status_notes],
      ["Task Notes", pickup.task_notes],
    ]),
  );

  backdrop.append(modal);
  root.append(backdrop);
}

function clearEscapeHandler(root) {
  if (root.opshopEscapeHandler) {
    document.removeEventListener("keydown", root.opshopEscapeHandler);
    root.opshopEscapeHandler = null;
  }
}

function createDetailSection(titleText, fields) {
  const section = document.createElement("section");
  section.className = "opshop-detail-section";

  const title = document.createElement("h3");
  title.textContent = titleText;

  const grid = document.createElement("dl");
  grid.className = "detail-grid";
  fields.forEach(([label, value]) => {
    grid.append(createDetailField(label, value));
  });

  section.append(title, grid);
  return section;
}

function formatBoolean(value) {
  if (value === undefined || value === null || value === "") {
    return "";
  }
  return value ? "Yes" : "No";
}
