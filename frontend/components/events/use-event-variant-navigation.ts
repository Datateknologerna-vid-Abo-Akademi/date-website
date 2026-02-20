"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  BASE_HASHES,
  HASH_ALIASES,
  normalizeHash,
  supportsVariantSections,
  usesHashNavigation,
  variantNavIncludesSectionLinks,
  type ActiveSection,
  type SectionKey,
  type VariantNavItem,
} from "@/components/events/event-variant-helpers";
import type { EventItem } from "@/lib/api/types";

interface UseEventVariantNavigationParams {
  event: EventItem;
}

export function useEventVariantNavigation({ event }: UseEventVariantNavigationParams) {
  const variant = event.template_variant ?? "default";
  const isSpecialVariant = variant !== "default";
  const useHash = usesHashNavigation(variant);
  const includeSectionLinks = variantNavIncludesSectionLinks(variant);
  const variantSections = useMemo(
    () => (supportsVariantSections(variant) ? event.variant_sections ?? [] : []),
    [event.variant_sections, variant],
  );

  const navItems = useMemo<VariantNavItem[]>(
    () => {
      if (!isSpecialVariant || !useHash) return [];
      return [
        { key: "main", label: "Välkommen" },
        ...(includeSectionLinks
          ? variantSections.map((section) => ({
              key: `page:${section.slug}` as SectionKey,
              label: section.title,
            }))
          : []),
        { key: "signup", label: "Anmälan" },
        { key: "attendees", label: "Anmälda" },
      ];
    },
    [includeSectionLinks, isSpecialVariant, useHash, variantSections],
  );

  const [activeSection, setActiveSection] = useState<ActiveSection>("main");

  useEffect(() => {
    if (!isSpecialVariant || !useHash) return;
    const knownSectionSlugs = new Set(variantSections.map((section) => section.slug.toLowerCase()));

    const updateFromHash = () => {
      const normalized = normalizeHash(window.location.hash);
      if (!normalized) {
        setActiveSection("main");
        return;
      }
      const aliased = HASH_ALIASES[normalized];
      if (aliased) {
        setActiveSection(aliased);
        return;
      }
      if (knownSectionSlugs.has(normalized)) {
        setActiveSection(`page:${normalized}`);
        return;
      }
      setActiveSection(isSpecialVariant ? "none" : "main");
    };

    updateFromHash();
    window.addEventListener("hashchange", updateFromHash);
    return () => window.removeEventListener("hashchange", updateFromHash);
  }, [isSpecialVariant, useHash, variantSections]);

  const sectionHash = useCallback((section: SectionKey) => {
    if (section === "main" || section === "signup" || section === "attendees") {
      return BASE_HASHES[section];
    }
    const slug = section.replace(/^page:/, "");
    return `#/${slug}`;
  }, []);

  const onSectionSelect = useCallback(
    (section: SectionKey) => {
      setActiveSection(section);
      window.history.replaceState(null, "", sectionHash(section));
    },
    [sectionHash],
  );

  const showMain = variant === "tomtejakt" ? true : !isSpecialVariant || activeSection === "main";
  const showSignup = variant === "tomtejakt" ? Boolean(event.sign_up) : !isSpecialVariant || activeSection === "signup";
  const showAttendees =
    variant === "tomtejakt" ? Boolean(event.sign_up) : !isSpecialVariant || activeSection === "attendees";

  return {
    activeSection,
    isSpecialVariant,
    navItems,
    onSectionSelect,
    sectionHash,
    showAttendees,
    showMain,
    showSignup,
    variant,
  };
}
