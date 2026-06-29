export function normalizeDeliveryOrderUrgency(value) {
  return String(value || "").trim().toLowerCase() === "urgent" ? "Urgent" : "Normal";
}


export function isDeliveryOrderUrgent(orderOrUrgency) {
  const urgency = typeof orderOrUrgency === "object" && orderOrUrgency !== null
    ? orderOrUrgency.urgency
    : orderOrUrgency;
  return normalizeDeliveryOrderUrgency(urgency) === "Urgent";
}


export function sortDeliveryTaskPoolOrders(orders) {
  return (orders || [])
    .map((order, originalIndex) => ({ order, originalIndex }))
    .sort((left, right) => compareOrderPriority(left, right))
    .map(({ order }) => order);
}


function compareOrderPriority(left, right) {
  const leftOrder = left.order || {};
  const rightOrder = right.order || {};
  const urgencyDifference = urgencyRank(leftOrder) - urgencyRank(rightOrder);
  if (urgencyDifference) {
    return urgencyDifference;
  }

  for (const compare of [
    compareOptionalIsoDate(leftOrder.delivery_date, rightOrder.delivery_date),
    compareOptionalTime(leftOrder.start_time, rightOrder.start_time),
    compareText(leftOrder.invoice_number, rightOrder.invoice_number),
    compareText(leftOrder.order_no, rightOrder.order_no),
    compareText(leftOrder.order_id, rightOrder.order_id),
  ]) {
    if (compare) {
      return compare;
    }
  }
  return left.originalIndex - right.originalIndex;
}


function urgencyRank(order) {
  return isDeliveryOrderUrgent(order) ? 0 : 1;
}


function compareOptionalIsoDate(left, right) {
  return compareOptionalNormalized(
    normalizeIsoDate(left),
    normalizeIsoDate(right),
  );
}


function compareOptionalTime(left, right) {
  return compareOptionalNormalized(
    normalizeTime(left),
    normalizeTime(right),
  );
}


function compareOptionalNormalized(left, right) {
  if (left && right) {
    return compareStrings(left, right);
  }
  if (left) {
    return -1;
  }
  if (right) {
    return 1;
  }
  return 0;
}


function normalizeIsoDate(value) {
  const text = String(value || "").trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!match) {
    return "";
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) {
    return "";
  }
  return text;
}


function daysInMonth(year, month) {
  if (month === 2) {
    const isLeapYear = year % 400 === 0 || (year % 4 === 0 && year % 100 !== 0);
    return isLeapYear ? 29 : 28;
  }
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}


function normalizeTime(value) {
  const text = String(value || "").trim();
  const match = /^(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(text);
  if (!match) {
    return "";
  }
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  const second = Number(match[3] || 0);
  if (hour > 23 || minute > 59 || second > 59) {
    return "";
  }
  return `${match[1]}:${match[2]}:${match[3] || "00"}`;
}


function compareText(left, right) {
  return compareStrings(
    String(left || "").trim().toUpperCase(),
    String(right || "").trim().toUpperCase(),
  );
}


function compareStrings(left, right) {
  if (left < right) {
    return -1;
  }
  if (left > right) {
    return 1;
  }
  return 0;
}
