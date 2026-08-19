export const DELIVERY_DRAG_EDGE_SIZE = 88;
export const DELIVERY_DRAG_MAX_SCROLL_SPEED_PX_PER_SECOND = 1320;
export const DELIVERY_DRAG_MAX_FRAME_DELTA_MS = 50;

export function deliveryDragScrollVelocity(
  clientY,
  viewportHeight,
  edgeSize = DELIVERY_DRAG_EDGE_SIZE,
  maxSpeedPxPerSecond = DELIVERY_DRAG_MAX_SCROLL_SPEED_PX_PER_SECOND,
) {
  const pointerY = Number(clientY);
  const height = Number(viewportHeight);
  if (!Number.isFinite(pointerY) || !Number.isFinite(height) || height <= 0) {
    return 0;
  }
  const zone = Math.min(Math.max(Number(edgeSize) || 0, 0), height / 2);
  const speed = Math.max(Number(maxSpeedPxPerSecond) || 0, 0);
  if (!zone || !speed) {
    return 0;
  }
  if (pointerY < zone) {
    return -speed * Math.min((zone - Math.max(pointerY, 0)) / zone, 1);
  }
  const bottomEdge = height - zone;
  if (pointerY > bottomEdge) {
    return speed * Math.min((Math.min(pointerY, height) - bottomEdge) / zone, 1);
  }
  return 0;
}

function defaultScrollState() {
  if (typeof document === "undefined") {
    return { scrollTop: 0, maxScrollTop: 0 };
  }
  const scrollOwner = document.scrollingElement || document.documentElement;
  return {
    scrollTop: scrollOwner?.scrollTop || 0,
    maxScrollTop: Math.max(
      (scrollOwner?.scrollHeight || 0) - (scrollOwner?.clientHeight || 0),
      0,
    ),
  };
}

export function createDeliveryDragAutoScroll({
  eventTarget = typeof document === "undefined" ? null : document,
  windowTarget = typeof window === "undefined" ? null : window,
  getViewportHeight = () => windowTarget?.innerHeight || 0,
  getScrollState = defaultScrollState,
  scrollBy = (deltaY) => windowTarget?.scrollBy(0, deltaY),
  requestFrame = (callback) => globalThis.requestAnimationFrame(callback),
  cancelFrame = (frameId) => globalThis.cancelAnimationFrame(frameId),
  edgeSize = DELIVERY_DRAG_EDGE_SIZE,
  maxSpeedPxPerSecond = DELIVERY_DRAG_MAX_SCROLL_SPEED_PX_PER_SECOND,
  maxFrameDeltaMs = DELIVERY_DRAG_MAX_FRAME_DELTA_MS,
} = {}) {
  let active = false;
  let latestClientY = null;
  let frameId = null;
  let previousFrameTimestamp = null;

  const currentVelocity = () => deliveryDragScrollVelocity(
    latestClientY,
    getViewportHeight(),
    edgeSize,
    maxSpeedPxPerSecond,
  );

  const cancelPendingFrame = () => {
    if (frameId !== null) {
      cancelFrame(frameId);
      frameId = null;
    }
  };

  const scheduleFrame = () => {
    if (active && frameId === null && currentVelocity() !== 0) {
      frameId = requestFrame(runFrame);
    }
  };

  function runFrame(timestamp) {
    frameId = null;
    if (!active) {
      return;
    }
    const velocity = currentVelocity();
    if (!velocity) {
      return;
    }
    const { scrollTop = 0, maxScrollTop = 0 } = getScrollState() || {};
    const remaining = velocity < 0
      ? Math.max(scrollTop, 0)
      : Math.max(maxScrollTop - scrollTop, 0);
    if (!remaining) {
      previousFrameTimestamp = null;
      return;
    }
    const currentTimestamp = Number(timestamp);
    if (!Number.isFinite(currentTimestamp)) {
      previousFrameTimestamp = null;
      scheduleFrame();
      return;
    }
    if (previousFrameTimestamp === null) {
      previousFrameTimestamp = currentTimestamp;
      scheduleFrame();
      return;
    }
    const elapsedMs = Math.min(
      Math.max(currentTimestamp - previousFrameTimestamp, 0),
      Math.max(Number(maxFrameDeltaMs) || 0, 0),
    );
    previousFrameTimestamp = currentTimestamp;
    if (!elapsedMs) {
      return;
    }
    const frameDistance = Math.abs(velocity) * elapsedMs / 1000;
    const deltaY = Math.sign(velocity) * Math.min(frameDistance, remaining);
    scrollBy(deltaY);
    if (Math.abs(deltaY) >= remaining) {
      previousFrameTimestamp = null;
      return;
    }
    scheduleFrame();
  }

  const handleDragOver = (event) => {
    if (!active || !Number.isFinite(Number(event?.clientY))) {
      return;
    }
    latestClientY = Number(event.clientY);
    if (currentVelocity() === 0) {
      cancelPendingFrame();
      previousFrameTimestamp = null;
      return;
    }
    scheduleFrame();
  };

  const stop = () => {
    active = false;
    latestClientY = null;
    previousFrameTimestamp = null;
    cancelPendingFrame();
    eventTarget?.removeEventListener("dragover", handleDragOver, true);
    eventTarget?.removeEventListener("dragend", stop, true);
    eventTarget?.removeEventListener("drop", stop, true);
    windowTarget?.removeEventListener("blur", stop, true);
  };

  const start = () => {
    stop();
    active = true;
    eventTarget?.addEventListener("dragover", handleDragOver, true);
    eventTarget?.addEventListener("dragend", stop, true);
    eventTarget?.addEventListener("drop", stop, true);
    windowTarget?.addEventListener("blur", stop, true);
  };

  return {
    isActive: () => active,
    start,
    stop,
  };
}

export const deliveryOrderDragAutoScroll = createDeliveryDragAutoScroll();
