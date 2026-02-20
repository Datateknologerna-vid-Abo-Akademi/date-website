const LEGACY_TIME_ZONE = "Europe/Helsinki";

export function toPreviewText(value: string, maxWords = 20) {
  const plain = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (!plain) return "";
  const words = plain.split(" ");
  if (words.length <= maxWords) return plain;
  return `${words.slice(0, maxWords).join(" ")}...`;
}

function formatDatePart(value: string, options: Intl.DateTimeFormatOptions) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("sv-FI", {
    ...options,
    timeZone: LEGACY_TIME_ZONE,
  }).format(date);
}

export function formatDay(value: string) {
  return formatDatePart(value, { day: "2-digit" });
}

export function formatMonth(value: string) {
  return formatDatePart(value, { month: "short" });
}

export function formatTime(value: string) {
  return formatDatePart(value, { hour: "2-digit", minute: "2-digit" });
}

export function formatWeekday(value: string) {
  return formatDatePart(value, { weekday: "short" });
}

export function formatParticipants(maxParticipants: number) {
  if (maxParticipants === 0) return "Ingen begransning";
  return String(maxParticipants);
}
