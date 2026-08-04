function formatLocalDateString(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getTodayLocalDateString(date = new Date()) {
  return formatLocalDateString(date);
}

export function getNextBusinessDayLocalDateString(date = new Date()) {
  const nextDate = new Date(date.getTime());
  const weekday = nextDate.getDay();
  const daysToAdd = weekday === 5 ? 3 : weekday === 6 ? 2 : 1;
  nextDate.setDate(nextDate.getDate() + daysToAdd);
  return formatLocalDateString(nextDate);
}
