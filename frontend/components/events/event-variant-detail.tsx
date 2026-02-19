"use client";

import { useEffect, useMemo, useState } from "react";

import { EventAttendeeList } from "@/components/events/event-attendee-list";
import { EventSignupForm } from "@/components/events/event-signup-form";
import { RichContent } from "@/components/rich-content";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";

type BaseSectionKey = "main" | "signup" | "attendees";
type SectionKey = BaseSectionKey | `page:${string}`;

interface EventVariantDetailProps {
  event: EventItem;
  attendeeData: EventAttendeeListPayload | null;
}

const HASH_ALIASES: Record<string, BaseSectionKey> = {
  main: "main",
  anmalan: "signup",
  "attendee-list": "attendees",
  anmalda: "attendees",
};

const BASE_HASHES: Record<BaseSectionKey, string> = {
  main: "#/main",
  signup: "#/anmalan",
  attendees: "#/attendee-list",
};

function normalizeHash(hash: string) {
  return hash.toLowerCase().replace(/^#\/?/, "").trim();
}

function variantTitle(variant: EventItem["template_variant"]) {
  switch (variant) {
    case "arsfest":
      return "Arsfest";
    case "baal":
      return "Kemistbaal";
    case "kk100":
      return "100 Kemistbaal";
    case "tomtejakt":
      return "Tomtejakt";
    case "wappmiddag":
      return "Teknologwappmiddag";
    default:
      return "Händelse";
  }
}

function formatDateTime(value: string) {
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

export function EventVariantDetail({ event, attendeeData }: EventVariantDetailProps) {
  const variant = event.template_variant ?? "default";
  const isSpecialVariant = variant !== "default";
  const variantSections = useMemo(() => event.variant_sections ?? [], [event.variant_sections]);

  const navItems = useMemo(
    () => [
      { key: "main" as SectionKey, label: "Välkommen" },
      ...variantSections.map((section) => ({
        key: `page:${section.slug}` as SectionKey,
        label: section.title,
      })),
      { key: "signup" as SectionKey, label: "Anmälan" },
      { key: "attendees" as SectionKey, label: "Anmälda" },
    ],
    [variantSections],
  );

  const [activeSection, setActiveSection] = useState<SectionKey>("main");

  useEffect(() => {
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
      setActiveSection("main");
    };

    updateFromHash();
    window.addEventListener("hashchange", updateFromHash);
    return () => window.removeEventListener("hashchange", updateFromHash);
  }, [variantSections]);

  function sectionHash(section: SectionKey) {
    if (section === "main" || section === "signup" || section === "attendees") {
      return BASE_HASHES[section];
    }
    const slug = section.replace(/^page:/, "");
    return `#/${slug}`;
  }

  function onSectionSelect(section: SectionKey) {
    setActiveSection(section);
    window.history.replaceState(null, "", sectionHash(section));
  }

  const showMain = !isSpecialVariant || activeSection === "main";
  const showSignup = !isSpecialVariant || activeSection === "signup";
  const showAttendees = !isSpecialVariant || activeSection === "attendees";

  return (
    <div className={`event-detail-page ${isSpecialVariant ? "event-variant-shell" : ""} event-variant--${variant}`}>
      <div
        className={`event-detail-background ${event.image_url ? "has-image" : ""}`}
        style={event.image_url ? { backgroundImage: `url(${event.image_url})` } : undefined}
      >
        <div className="container-md min-vh-100 p-1 event-detail-shell">
          <div className="container-size event-detail-container">
            <section className={`content event-detail-content ${showMain ? "" : "is-hidden"}`}>
              {isSpecialVariant ? <h4 className="help-text">{variantTitle(event.template_variant)}</h4> : null}
              <h2 className="header">{event.title}</h2>
              <h4 className="help-text">{formatDateTime(event.event_date_start)}</h4>
              {event.redirect_link ? (
                <p>
                  Extern anmälningslänk:{" "}
                  <a href={event.redirect_link} target="_blank" rel="noreferrer">
                    {event.redirect_link}
                  </a>
                </p>
              ) : null}
              <RichContent html={event.content} />
            </section>

            {isSpecialVariant ? (
              <nav className="event-variant-nav" aria-label="Event sections">
                {navItems.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={activeSection === item.key ? "is-active" : ""}
                    onClick={() => onSectionSelect(item.key)}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
            ) : null}

            {variantSections.map((section) => {
              const sectionKey = `page:${section.slug}` as SectionKey;
              const shouldShow = !isSpecialVariant || activeSection === sectionKey;
              return (
                <section key={section.slug} className={`content event-detail-content ${shouldShow ? "" : "is-hidden"}`}>
                  <h2>{section.title}</h2>
                  <RichContent html={section.content} />
                </section>
              );
            })}

            <section id="sign-up" className={`content event-detail-content ${showSignup ? "" : "is-hidden"}`}>
              <h2>Anmälning</h2>
              {event.redirect_link ? (
                <p className="meta">Detta evenemang använder extern anmälning.</p>
              ) : (
                <EventSignupForm event={event} />
              )}
            </section>

            <section id="attendee-list" className={`content event-detail-content overflow-auto ${showAttendees ? "" : "is-hidden"}`}>
              <EventAttendeeList data={attendeeData} />
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
