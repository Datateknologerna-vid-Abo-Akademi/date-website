const LEGACY_TIME_ZONE = "Europe/Helsinki";

function formatLegacyDatePart(value: string | null, options: Intl.DateTimeFormatOptions) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("sv-FI", {
    ...options,
    timeZone: LEGACY_TIME_ZONE,
  }).format(date);
}

export function formatDate(value: string | null) {
  return formatLegacyDatePart(value, { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDay(value: string | null) {
  return formatLegacyDatePart(value, { day: "2-digit" });
}

export function formatMonth(value: string | null) {
  return formatLegacyDatePart(value, { month: "short" });
}

export function formatWeekday(value: string | null) {
  return formatLegacyDatePart(value, { weekday: "short" });
}

export function formatTime(value: string | null) {
  return formatLegacyDatePart(value, { hour: "2-digit", minute: "2-digit" });
}

function getTagline(associationName: string, associationFullName: string) {
  if (!associationFullName) return "";
  const prefixPattern = new RegExp(`^${associationName}\\s*`, "i");
  const tagline = associationFullName.replace(prefixPattern, "").trim();
  return tagline || associationFullName;
}

export function getHeroSubtitle(
  brand: string,
  associationName: string,
  associationFullName: string,
) {
  if (brand === "biocum") {
    return "vid Åbo Akademi";
  }
  return getTagline(associationName, associationFullName);
}

export function toPreviewText(value: string, maxWords = 28) {
  const plain = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (!plain) return "";
  const words = plain.split(" ");
  if (words.length <= maxWords) return plain;
  return `${words.slice(0, maxWords).join(" ")}...`;
}

export function getAboutText(brand: string) {
  if (brand === "date") {
    return "Datateknologerna vid Åbo Akademi rf är en förening för studerande vid utbildningsprogrammet i datateknik vid Fakulteten för Naturvetenskaper och Teknik vid Åbo Akademi, samt för studerande vid övriga tekniskt inriktade utbildningslinjer i databehandling. Föreningen grundades 1999, närmare bestämt den 24.8 kl. 16:32. Medlemmarna känns igen på deras svarta halare och stiliga tofsmössor.";
  }
  if (brand === "demo") {
    return "DaTe demo website, contact datedatorer@gmail.com if you have questions.";
  }
  return "";
}
