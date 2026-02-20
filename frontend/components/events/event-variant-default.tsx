import { EventAttendeeList } from "@/components/events/event-attendee-list";
import { EventDetailShell } from "@/components/events/event-detail-shell";
import { EventSignupForm } from "@/components/events/event-signup-form";
import { formatDateTime } from "@/components/events/event-variant-helpers";
import { RichContent } from "@/components/rich-content";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";
import styles from "./event-variant-default.module.css";

interface EventVariantDefaultProps {
  event: EventItem;
  attendeeData: EventAttendeeListPayload | null;
  projectName?: string;
}

export function EventVariantDefault({ event, attendeeData, projectName }: EventVariantDefaultProps) {
  const isON = projectName?.toLowerCase() === "on";
  const pageClassName = `event-detail-page event-variant--default ${styles.pageRoot} ${isON ? "event-variant--on-index" : ""}`;
  const backgroundClassName = `event-detail-background ${event.image_url || isON ? "has-image" : ""}`;
  const containerClassName = `container-size event-detail-container ${isON ? "container-margin-top pt-12" : ""}`;

  return (
    <EventDetailShell
      pageClassName={pageClassName}
      backgroundClassName={backgroundClassName}
      containerClassName={containerClassName}
      backgroundImageUrl={event.image_url}
    >
      <section className={`content event-detail-content ${styles.detailContent}`}>
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

      <section id="sign-up" className={`content event-detail-content ${styles.detailContent}`}>
        <h2>Anmälning</h2>
        {event.redirect_link ? (
          <p className="meta">Detta evenemang använder extern anmälning.</p>
        ) : (
          <EventSignupForm event={event} />
        )}
      </section>

      <section id="attendee-list" className={`content event-detail-content overflow-auto ${styles.detailContent}`}>
        <EventAttendeeList data={attendeeData} useVariantTemplateCopy={false} />
      </section>
    </EventDetailShell>
  );
}
