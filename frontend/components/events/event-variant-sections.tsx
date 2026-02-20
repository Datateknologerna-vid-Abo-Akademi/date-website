import { EventAttendeeList } from "@/components/events/event-attendee-list";
import { EventSignupForm } from "@/components/events/event-signup-form";
import { formatDateTime, type SectionKey } from "@/components/events/event-variant-helpers";
import { RichContent } from "@/components/rich-content";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";
import styles from "./event-variant-themed.module.css";

interface MainAndPagesProps {
  event: EventItem;
  variantContentClass: string;
  showMain: boolean;
  activeSection: SectionKey | "none";
}

export function EventVariantMainAndPages({
  event,
  variantContentClass,
  showMain,
  activeSection,
}: MainAndPagesProps) {
  const renderedVariantSections = event.variant_sections ?? [];

  return (
    <div className={event.template_variant === "arsfest" ? styles.lavaContainer : ""}>
      <section className={`${variantContentClass} ${showMain ? "" : styles.hidden}`}>
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
          <section
            key={section.slug}
            className={`${variantContentClass} ${section.slug} ${shouldShow ? "" : styles.hidden}`}
          >
            <h1>{section.title}</h1>
            <RichContent html={section.content} />
          </section>
        );
      })}
    </div>
  );
}

interface SignupSectionProps {
  event: EventItem;
  variantContentClass: string;
  showSignup: boolean;
}

export function EventVariantSignupSection({
  event,
  variantContentClass,
  showSignup,
}: SignupSectionProps) {
  return (
    <section id="sign-up" className={`${variantContentClass} anmalan break-words ${showSignup ? "" : styles.hidden}`}>
      <h2>Anmälning</h2>
      {event.redirect_link ? (
        <p className="meta">Detta evenemang använder extern anmälning.</p>
      ) : (
        <EventSignupForm event={event} />
      )}
    </section>
  );
}

interface AttendeeSectionProps {
  attendeeData: EventAttendeeListPayload | null;
  variantContentClass: string;
  showAttendees: boolean;
}

export function EventVariantAttendeeSection({
  attendeeData,
  variantContentClass,
  showAttendees,
}: AttendeeSectionProps) {
  return (
    <section
      id="attendee-list"
      className={`${variantContentClass} attendee-list overflow-auto ${showAttendees ? "" : styles.hidden}`}
    >
      <EventAttendeeList data={attendeeData} useVariantTemplateCopy />
    </section>
  );
}
