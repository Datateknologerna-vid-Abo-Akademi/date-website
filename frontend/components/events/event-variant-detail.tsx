"use client";

import { useEffect, useMemo, useState } from "react";

import { EventAttendeeList } from "@/components/events/event-attendee-list";
import { EventSignupForm } from "@/components/events/event-signup-form";
import { RichContent } from "@/components/rich-content";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";

type VariantSection = "main" | "signup" | "attendees";

interface EventVariantDetailProps {
  event: EventItem;
  attendeeData: EventAttendeeListPayload | null;
}

const HASH_TO_SECTION: Record<string, VariantSection> = {
  "#/main": "main",
  "#main": "main",
  "#/anmalan": "signup",
  "#anmalan": "signup",
  "#/attendee-list": "attendees",
  "#attendee-list": "attendees",
  "#/anmalda": "attendees",
  "#anmalda": "attendees",
};

const SECTION_TO_HASH: Record<VariantSection, string> = {
  main: "#/main",
  signup: "#/anmalan",
  attendees: "#/attendee-list",
};

function resolveSectionFromHash(hash: string): VariantSection {
  return HASH_TO_SECTION[hash.toLowerCase()] ?? "main";
}

function variantTitle(variant: EventItem["template_variant"]) {
  switch (variant) {
    case "arsfest":
      return "Årsfest";
    case "baal":
      return "Kemistbaal";
    case "kk100":
      return "100 Kemistbaal";
    case "tomtejakt":
      return "Tomtejakt";
    case "wappmiddag":
      return "Teknologwappmiddag";
    default:
      return "Event";
  }
}

export function EventVariantDetail({ event, attendeeData }: EventVariantDetailProps) {
  const [activeSection, setActiveSection] = useState<VariantSection>("main");

  useEffect(() => {
    const updateFromHash = () => {
      setActiveSection(resolveSectionFromHash(window.location.hash));
    };
    updateFromHash();
    window.addEventListener("hashchange", updateFromHash);
    return () => window.removeEventListener("hashchange", updateFromHash);
  }, []);

  const variant = event.template_variant ?? "default";
  const isSpecialVariant = variant !== "default";
  const navItems = useMemo(
    () => [
      { key: "main" as const, label: "Välkommen" },
      { key: "signup" as const, label: "Anmälan" },
      { key: "attendees" as const, label: "Anmälda" },
    ],
    [],
  );

  function onSectionSelect(section: VariantSection) {
    setActiveSection(section);
    window.history.replaceState(null, "", SECTION_TO_HASH[section]);
  }

  const showMain = !isSpecialVariant || activeSection === "main";
  const showSignup = !isSpecialVariant || activeSection === "signup";
  const showAttendees = !isSpecialVariant || activeSection === "attendees";

  return (
    <div className={`page-shell ${isSpecialVariant ? "event-variant-shell" : ""} event-variant--${variant}`}>
      <section className={`hero compact ${isSpecialVariant ? "event-variant-hero" : ""}`}>
        <p className="eyebrow">{variantTitle(event.template_variant)}</p>
        <h1>{event.title}</h1>
        <p className="meta">
          {new Date(event.event_date_start).toLocaleString()} - {new Date(event.event_date_end).toLocaleString()}
        </p>
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

      <section className={`panel ${showMain ? "" : "is-hidden"}`}>
        {event.redirect_link ? (
          <p>
            External registration link:{" "}
            <a href={event.redirect_link} target="_blank" rel="noreferrer">
              {event.redirect_link}
            </a>
          </p>
        ) : null}
        <RichContent html={event.content} />
      </section>

      <section className={`panel ${showSignup ? "" : "is-hidden"}`}>
        <h2>Anmälan</h2>
        {event.redirect_link ? (
          <p className="meta">This event uses an external registration link.</p>
        ) : (
          <EventSignupForm event={event} />
        )}
      </section>

      <section className={`panel ${showAttendees ? "" : "is-hidden"}`}>
        <h2>Anmälda</h2>
        <EventAttendeeList data={attendeeData} />
      </section>
    </div>
  );
}
