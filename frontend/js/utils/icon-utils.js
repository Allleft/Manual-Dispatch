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
  "chevron-down": [
    "m6 9 6 6 6-6",
  ],
  "chevron-up": [
    "m18 15-6-6-6 6",
  ],
  clock: [
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
    "M12 7.5V12l3 2",
  ],
  eye: [
    "M3.5 12s3-5.5 8.5-5.5S20.5 12 20.5 12s-3 5.5-8.5 5.5S3.5 12 3.5 12Z",
    "M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  ],
  home: [
    "M4 11.5 12 4l8 7.5",
    "M6.5 10.5V20h11v-9.5",
    "M10 20v-5h4v5",
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
  key: [
    "M15 8a4 4 0 1 1-1.17 2.83L5 19.66 3.5 18.16 12.34 9.33A4 4 0 0 1 15 8Z",
    "M7.5 17.5 9 19",
    "M10 15 11.5 16.5",
  ],
  list: [
    "M8 6h12",
    "M8 12h12",
    "M8 18h12",
    "M4 6h.01",
    "M4 12h.01",
    "M4 18h.01",
  ],
  location: [
    "M12 21s7-5.2 7-11a7 7 0 0 0-14 0c0 5.8 7 11 7 11Z",
    "M12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  ],
  pencil: [
    "M4 20h4.5L19 9.5 14.5 5 4 15.5V20Z",
    "m13.5 6.5 4 4",
  ],
  phone: [
    "M8 4.5 10.2 8 8.8 9.4c1 2 2.8 3.8 4.8 4.8l1.4-1.4 3.5 2.2-1.5 3.3c-.3.7-1.1 1.1-1.9.9C9.5 18 5.9 14.4 4.8 8.9c-.2-.8.2-1.6.9-1.9L8 4.5Z",
  ],
  plus: [
    "M12 5v14",
    "M5 12h14",
  ],
  refresh: [
    "M20 12a8 8 0 0 1-13.66 5.66",
    "M4 12A8 8 0 0 1 17.66 6.34",
    "M18 3v4h-4",
    "M6 21v-4h4",
  ],
  route: [
    "M6 6h.01",
    "M18 18h.01",
    "M7 6h4a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h8",
  ],
  search: [
    "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z",
    "m16 16 4 4",
  ],
  store: [
    "M5 9.5h14l-1-5H6l-1 5Z",
    "M6.5 9.5v10h11v-10",
    "M9 19.5v-5h6v5",
    "M4.5 9.5c0 1.4 1.1 2.5 2.5 2.5s2.5-1.1 2.5-2.5",
    "M9.5 9.5c0 1.4 1.1 2.5 2.5 2.5s2.5-1.1 2.5-2.5",
    "M14.5 9.5c0 1.4 1.1 2.5 2.5 2.5s2.5-1.1 2.5-2.5",
  ],
  tag: [
    "M4 11V4h7l9 9-7 7-9-9Z",
    "M8 8h.01",
  ],
  tree: [
    "M12 3 6.5 10h3L5 16h5v5h4v-5h5l-4.5-6h3L12 3Z",
  ],
  trash: [
    "M5 7h14",
    "M10 11v6",
    "M14 11v6",
    "M8 7l1-3h6l1 3",
    "M7 7l1 13h8l1-13",
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
  users: [
    "M9.5 11.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
    "M2.5 20a7 7 0 0 1 14 0",
    "M16.5 11.5a3 3 0 1 0-1.2-5.75",
    "M18 20a5.5 5.5 0 0 0-4.2-5.34",
  ],
  x: [
    "M6 6l12 12",
    "M18 6 6 18",
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
