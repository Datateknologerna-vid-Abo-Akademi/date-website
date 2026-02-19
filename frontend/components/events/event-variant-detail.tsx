"use client";

import { useEffect, useMemo, useState } from "react";

import { EventAttendeeList } from "@/components/events/event-attendee-list";
import { EventSignupForm } from "@/components/events/event-signup-form";
import { RichContent } from "@/components/rich-content";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";

type BaseSectionKey = "main" | "signup" | "attendees";
type SectionKey = BaseSectionKey | `page:${string}`;
type ActiveSection = SectionKey | "none";

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

function variantHeading(variant: EventItem["template_variant"]) {
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

function variantNavClass(variant: EventItem["template_variant"]) {
  return variant === "arsfest" ? "ball-nav flex-container-center" : "baal-nav";
}

function variantLinkClass(variant: EventItem["template_variant"]) {
  return variant === "arsfest" ? "ball-link" : "baal-link";
}

function supportsVariantSections(variant: EventItem["template_variant"]) {
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

function variantNavIncludesSectionLinks(variant: EventItem["template_variant"]) {
  switch (variant) {
    case "arsfest":
    case "baal":
    case "kk100":
      return true;
    default:
      return false;
  }
}

function usesHashNavigation(variant: EventItem["template_variant"]) {
  return variant !== "tomtejakt";
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
  const renderedVariantSections = useMemo(
    () => (supportsVariantSections(variant) ? variantSections : []),
    [variant, variantSections],
  );
  const includeSectionLinksInNav = variantNavIncludesSectionLinks(variant);
  const useHashNavigation = usesHashNavigation(variant);

  const navItems = useMemo(
    () => {
      if (!isSpecialVariant || !useHashNavigation) return [];
      return [
        { key: "main" as SectionKey, label: "Välkommen" },
        ...(includeSectionLinksInNav
          ? renderedVariantSections.map((section) => ({
              key: `page:${section.slug}` as SectionKey,
              label: section.title,
            }))
          : []),
        { key: "signup" as SectionKey, label: "Anmälan" },
        { key: "attendees" as SectionKey, label: "Anmälda" },
      ];
    },
    [includeSectionLinksInNav, isSpecialVariant, renderedVariantSections, useHashNavigation],
  );

  const [activeSection, setActiveSection] = useState<ActiveSection>("main");

  useEffect(() => {
    if (!isSpecialVariant || !useHashNavigation) return;

    const knownSectionSlugs = new Set(renderedVariantSections.map((section) => section.slug.toLowerCase()));

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
  }, [isSpecialVariant, renderedVariantSections, useHashNavigation]);

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

  const showMain = variant === "tomtejakt" ? true : !isSpecialVariant || activeSection === "main";
  const showSignup = variant === "tomtejakt" ? Boolean(event.sign_up) : !isSpecialVariant || activeSection === "signup";
  const showAttendees =
    variant === "tomtejakt" ? Boolean(event.sign_up) : !isSpecialVariant || activeSection === "attendees";

  if (!isSpecialVariant) {
    return (
      <div className="event-detail-page event-variant--default">
        <div
          className={`event-detail-background ${event.image_url ? "has-image" : ""}`}
          style={event.image_url ? { backgroundImage: `url(${event.image_url})` } : undefined}
        >
          <div className="container-md min-vh-100 p-1 event-detail-shell">
            <div className="container-size event-detail-container">
              <section className="content event-detail-content">
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

              <section id="sign-up" className="content event-detail-content">
                <h2>Anmälning</h2>
                {event.redirect_link ? (
                  <p className="meta">Detta evenemang använder extern anmälning.</p>
                ) : (
                  <EventSignupForm event={event} />
                )}
              </section>

              <section id="attendee-list" className="content event-detail-content overflow-auto">
                <EventAttendeeList data={attendeeData} useVariantTemplateCopy={false} />
              </section>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (variant === "tomtejakt") {
    return (
      <div className="event-detail-page event-variant-shell event-variant--tomtejakt">
        <div className="event-detail-background background-img">
          <div className="container-md min-vh-100 p-1 event-detail-shell">
            <div className="container-size event-detail-container tomtejakt-event-container">
              <section className="content tomtejakt-content">
                <div className="tomte-header">
                  <div className="header-span">
                    <span className="text">TOMTEJAKT</span>
                    <span className="sitting-elf icon">
                      <img src="/static/events/img/tomtejakt-sitting-elf.svg" alt="" aria-hidden="true" />
                    </span>
                  </div>
                  <div className="tree-svg">
                    <img src="/static/events/img/tomtejakt-tree.svg" alt="" aria-hidden="true" />
                  </div>
                  <div className="elf-svg">
                    <img src="/static/events/img/tomtejakt-elf.svg" alt="" aria-hidden="true" />
                  </div>
                </div>
                <h2 className="header">{event.title}</h2>
                <h4 className="help-text">{formatDateTime(event.event_date_start)}</h4>
                <RichContent html={event.content} />
              </section>

              {event.sign_up ? (
                <>
                  <section id="sign-up" className="content tomtejakt-content">
                    <h2>Anmälning</h2>
                    {event.redirect_link ? (
                      <p className="meta">Detta evenemang använder extern anmälning.</p>
                    ) : (
                      <EventSignupForm event={event} />
                    )}
                  </section>

                  <section id="attendee-list" className="content tomtejakt-content overflow-auto">
                    <EventAttendeeList data={attendeeData} useVariantTemplateCopy />
                  </section>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const variantContentClass = variant === "arsfest" ? "ball-content" : "baal-content";
  const linkClass = variantLinkClass(event.template_variant);

  return (
    <div className={`event-detail-page event-variant-shell event-variant--${variant}`}>
      <div
        className={`event-detail-background background-img ${event.image_url ? "has-image" : ""}`}
        style={event.image_url ? { backgroundImage: `url(${event.image_url})` } : undefined}
      >
        <div className="container-md min-vh-100 p-1 event-detail-shell">
          <div
            className={`container-size event-detail-container ${
              variant === "arsfest" ? "lava-container lava-container-bottom" : ""
            }`}
          >
            <div className="content header-box">
              {variant === "arsfest" ? (
                <div className="main-content mt-4">
                  <div className="text-center flex-container-center">
                    <div className="periodic-table-square glowing-text-orange">
                      <div className="periodic-table-inner">
                        <div className="periodic-table-number-container card-shine-effect">
                          <h2>26</h2>
                        </div>
                        <h2 className="age card-shine-effect">DaTe</h2>
                        <div className="periodic-table-date-container card-shine-effect">
                          <h2>Årsfest 22.2.2025</h2>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : variant === "wappmiddag" ? (
                <>
                  <img className="balloon balloon-left" src="/static/core/images/ballong_black.png" alt="balloon" />
                  <img className="balloon balloon-right" src="/static/core/images/ballong_black.png" alt="balloon" />
                  <img className="header-logo wappmiddag-header-logo" src="/static/events/img/wappmiddag-header.svg" alt="" aria-hidden="true" />
                  <h1 className="baal-header">{variantHeading(event.template_variant)}</h1>
                </>
              ) : (
                <>
                  {variant === "baal" && (
                    <img className="header-logo" src="/static/core/images/HQKK_2.png" alt={variantHeading(event.template_variant)} />
                  )}
                  {variant === "kk100" && (
                    <img className="header-logo" src="/static/core/images/100logogold.png" alt={variantHeading(event.template_variant)} />
                  )}
                  {variantHeading(event.template_variant) ? <h1 className="baal-header">{variantHeading(event.template_variant)}</h1> : null}
                </>
              )}

              {navItems.length > 0 ? (
                <div className={variantNavClass(event.template_variant)}>
                  {navItems.map((item) => (
                    <a
                      key={item.key}
                      className={`${linkClass} ${activeSection === item.key ? "is-active" : ""}`}
                      href={sectionHash(item.key)}
                      onClick={(domEvent) => {
                        domEvent.preventDefault();
                        onSectionSelect(item.key);
                      }}
                    >
                      {item.label}
                    </a>
                  ))}
                </div>
              ) : null}
            </div>

            <div className={`text-content ${variant === "arsfest" ? "lava-container" : ""}`}>
              <section className={`content ${variantContentClass} main ${showMain ? "" : "hidden"}`}>
                <h1 className="header">{event.title}</h1>
                <h4>{formatDateTime(event.event_date_start)}</h4>
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

              {renderedVariantSections.map((section) => {
                const sectionKey = `page:${section.slug}` as SectionKey;
                const shouldShow = activeSection === sectionKey;
                return (
                  <section key={section.slug} className={`content ${variantContentClass} ${section.slug} ${shouldShow ? "" : "hidden"}`}>
                    <h1>{section.title}</h1>
                    <RichContent html={section.content} />
                  </section>
                );
              })}
            </div>

            <section id="sign-up" className={`content ${variantContentClass} anmalan break-words ${showSignup ? "" : "hidden"}`}>
              <h2>Anmälning</h2>
              {event.redirect_link ? (
                <p className="meta">Detta evenemang använder extern anmälning.</p>
              ) : (
                <EventSignupForm event={event} />
              )}
            </section>

            <section
              id="attendee-list"
              className={`content ${variantContentClass} attendee-list overflow-auto ${showAttendees ? "" : "hidden"}`}
            >
              <EventAttendeeList data={attendeeData} useVariantTemplateCopy />
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
