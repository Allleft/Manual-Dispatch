const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

const ICON_PATHS = {
  "arrow-right": [
    "M5 12h14",
    "m13 6 6 6-6 6",
  ],
  bag: [
    "M6.5 8.5h11l1 11h-13l1-11Z",
    "M9 8.5a3 3 0 0 1 6 0",
  ],
  box: [
    "m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z",
    "M4 7.5 12 12l8-4.5",
    "M12 12v9",
  ],
  calendar: [
    "M7 3v3",
    "M17 3v3",
    "M4.5 8.5h15",
    "M5.5 5h13A1.5 1.5 0 0 1 20 6.5v12A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-12A1.5 1.5 0 0 1 5.5 5Z",
  ],
  check: [
    "m5 12 4.2 4.2L19 6.5",
  ],
  "cloud-upload": [
    "M8 17H7a4 4 0 0 1-.7-7.94A5.5 5.5 0 0 1 17 8.5h.5A3.5 3.5 0 0 1 18 15.96",
    "M12 19V11",
    "m8.5 14.5 3.5-3.5 3.5 3.5",
  ],
  document: [
    "M7 3.5h6.5L18 8v12.5H7V3.5Z",
    "M13.5 3.5V8H18",
    "M9.5 12h5",
    "M9.5 15h5",
  ],
  eye: [
    "M3.5 12s3-5.5 8.5-5.5S20.5 12 20.5 12s-3 5.5-8.5 5.5S3.5 12 3.5 12Z",
    "M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  ],
  history: [
    "M4 12a8 8 0 1 0 2.35-5.65",
    "M4 5.5v4h4",
    "M12 8v5l3 2",
  ],
  info: [
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
    "M12 10.5v5",
    "M12 7.5h.01",
  ],
  list: [
    "M8 6h12",
    "M8 12h12",
    "M8 18h12",
    "M4 6h.01",
    "M4 12h.01",
    "M4 18h.01",
  ],
  phone: [
    "M8 4.5 10.2 8 8.8 9.4c1 2 2.8 3.8 4.8 4.8l1.4-1.4 3.5 2.2-1.5 3.3c-.3.7-1.1 1.1-1.9.9C9.5 18 5.9 14.4 4.8 8.9c-.2-.8.2-1.6.9-1.9L8 4.5Z",
  ],
  plus: [
    "M12 5v14",
    "M5 12h14",
  ],
  tree: [
    "M12 3 6.5 10h3L5 16h5v5h4v-5h5l-4.5-6h3L12 3Z",
  ],
  truck: [
    "M3.5 6.5h10v8h-10v-8Z",
    "M13.5 9h3.5l3 3.5v2h-6.5V9Z",
    "M7 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
    "M17 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  ],
  user: [
    "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
    "M4.5 20a7.5 7.5 0 0 1 15 0",
  ],
};

export function createIcon(name, className = "") {
  const svg = document.createElementNS(SVG_NAMESPACE, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("stroke-width", "2");
  svg.classList.add("ui-icon", `ui-icon-${name}`);
  className
    .split(" ")
    .filter(Boolean)
    .forEach((token) => svg.classList.add(token));

  (ICON_PATHS[name] || ICON_PATHS.info).forEach((pathData) => {
    const path = document.createElementNS(SVG_NAMESPACE, "path");
    path.setAttribute("d", pathData);
    svg.append(path);
  });

  return svg;
}
