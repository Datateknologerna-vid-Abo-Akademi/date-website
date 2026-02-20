import type { EventItem } from "@/lib/api/types";

export type BaseSectionKey = "main" | "signup" | "attendees";
export type SectionKey = BaseSectionKey | `page:${string}`;
export type ActiveSection = SectionKey | "none";

export interface VariantNavItem {
  key: SectionKey;
  label: string;
}

export const HASH_ALIASES: Record<string, BaseSectionKey> = {
  main: "main",
  anmalan: "signup",
  "attendee-list": "attendees",
  anmalda: "attendees",
};

export const BASE_HASHES: Record<BaseSectionKey, string> = {
  main: "#/main",
  signup: "#/anmalan",
  attendees: "#/attendee-list",
};

export function normalizeHash(hash: string) {
  return hash.toLowerCase().replace(/^#\/?/, "").trim();
}

export function variantHeading(variant: EventItem["template_variant"]) {
  switch (variant) {
    case "arsfest":
      return "Arsfest";
    case "baal":
      return "CII Kemistbaal";
    case "kk100":
      return "100 Kemistbaal";
    case "tomtejakt":
      return "Tomtejakt";
    case "wappmiddag":
      return "Teknologwappmiddag";
    default:
      return "";
  }
}

export function supportsVariantSections(variant: EventItem["template_variant"]) {
  switch (variant) {
    case "arsfest":
    case "baal":
    case "kk100":
    case "wappmiddag":
      return true;
    default:
      return false;
  }
}

export function variantNavIncludesSectionLinks(variant: EventItem["template_variant"]) {
  switch (variant) {
    case "arsfest":
    case "baal":
    case "kk100":
      return true;
    default:
      return false;
  }
}

export function usesHashNavigation(variant: EventItem["template_variant"]) {
  return variant !== "tomtejakt";
}

export function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("sv-FI", {
    weekday: "long",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Helsinki",
  });
}
