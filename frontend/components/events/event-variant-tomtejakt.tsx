/* eslint-disable @next/next/no-img-element */
import { EventAttendeeList } from "@/components/events/event-attendee-list";
import { EventDetailShell } from "@/components/events/event-detail-shell";
import { EventSignupForm } from "@/components/events/event-signup-form";
import { formatDateTime } from "@/components/events/event-variant-helpers";
import { RichContent } from "@/components/rich-content";
import type { EventAttendeeListPayload, EventItem } from "@/lib/api/types";
import styles from "./event-variant-tomtejakt.module.css";

interface EventVariantTomtejaktProps {
  event: EventItem;
  attendeeData: EventAttendeeListPayload | null;
}

export function EventVariantTomtejakt({ event, attendeeData }: EventVariantTomtejaktProps) {
  return (
    <EventDetailShell
      pageClassName={`event-detail-page event-variant-shell event-variant--tomtejakt ${styles.pageRoot}`}
      backgroundClassName={`event-detail-background background-img ${styles.background}`}
      containerClassName={`container-size event-detail-container ${styles.container}`}
    >
      <section className={styles.content}>
        <div className={styles.header}>
          <div className="header-span">
            <span className={styles.text}>TOMTEJAKT</span>
            <span className={`${styles.sittingElf} ${styles.icon}`}>
              <img src="/static/events/img/tomtejakt-sitting-elf.svg" alt="" aria-hidden="true" />
            </span>
          </div>
          <div className={styles.tree}>
            <img src="/static/events/img/tomtejakt-tree.svg" alt="" aria-hidden="true" />
          </div>
          <div className={styles.elf}>
            <img src="/static/events/img/tomtejakt-elf.svg" alt="" aria-hidden="true" />
          </div>
        </div>
        <h2 className="header">{event.title}</h2>
        <h4 className="help-text">{formatDateTime(event.event_date_start)}</h4>
        <RichContent html={event.content} />
      </section>

      {event.sign_up ? (
        <>
          <section id="sign-up" className={styles.content}>
            <h2>Anmälning</h2>
            {event.redirect_link ? (
              <p className="meta">Detta evenemang använder extern anmälning.</p>
            ) : (
              <EventSignupForm event={event} />
            )}
          </section>

          <section id="attendee-list" className={`${styles.content} overflow-auto`}>
            <EventAttendeeList data={attendeeData} useVariantTemplateCopy />
          </section>
        </>
      ) : null}
    </EventDetailShell>
  );
}
