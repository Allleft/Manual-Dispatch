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
