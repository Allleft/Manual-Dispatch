export function captureElementScroll(rootSelector) {
  const selectors = [
    rootSelector,
    `${rootSelector} .detail-backdrop`,
    `${rootSelector} .opshop-pickup-list-modal`,
  ];

  return selectors.map((selector) => {
    const element = document.querySelector(selector);
    return {
      selector,
      scrollTop: element ? element.scrollTop : 0,
      scrollLeft: element ? element.scrollLeft : 0,
    };
  });
}


export function restoreElementScroll(snapshot) {
  if (!Array.isArray(snapshot)) {
    return;
  }

  const restore = () => {
    snapshot.forEach((item) => {
      const element = document.querySelector(item.selector);
      if (element) {
        element.scrollTop = item.scrollTop;
        element.scrollLeft = item.scrollLeft;
      }
    });
  };

  requestAnimationFrame(() => {
    restore();
    requestAnimationFrame(restore);
  });
}


export function captureWindowScroll() {
  if (typeof window === "undefined") {
    return { scrollX: 0, scrollY: 0 };
  }
  return {
    scrollX: window.scrollX || 0,
    scrollY: window.scrollY || 0,
  };
}


export function restoreWindowScroll(snapshot) {
  if (
    typeof window === "undefined" ||
    typeof window.scrollTo !== "function" ||
    !snapshot
  ) {
    return;
  }
  const restore = () => window.scrollTo(snapshot.scrollX, snapshot.scrollY);
  if (typeof requestAnimationFrame !== "function") {
    restore();
    return;
  }
  requestAnimationFrame(() => {
    restore();
    requestAnimationFrame(restore);
  });
}
