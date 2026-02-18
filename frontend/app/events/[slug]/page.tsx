import { notFound } from "next/navigation";

import { EventAttendeeList } from "@/components/events/event-attendee-list";
import { EventSignupForm } from "@/components/events/event-signup-form";
import { RichContent } from "@/components/rich-content";
import { getEvent, getEventAttendees } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface EventDetailPageProps {
  params: {
    slug: string;
  };
}

export default async function EventDetailPage({ params }: EventDetailPageProps) {
  await ensureModuleEnabled("events");
  const { slug } = params;
  const [event, attendeeData] = await Promise.all([
    getEvent(slug).catch(() => null),
    getEventAttendees(slug).catch(() => null),
  ]);
  if (!event) {
    notFound();
  }
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Event</p>
        <h1>{event.title}</h1>
        <p className="meta">
          {new Date(event.event_date_start).toLocaleString()} -{" "}
          {new Date(event.event_date_end).toLocaleString()}
        </p>
        {event.template_variant && event.template_variant !== "default" ? (
          <p className="meta">Template variant: {event.template_variant}</p>
        ) : null}
      </section>
      <section className="panel">
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
      <section className="panel">
        <h2>Registration</h2>
        {event.redirect_link ? (
          <p className="meta">This event uses an external registration link.</p>
        ) : (
          <EventSignupForm event={event} />
        )}
      </section>
      <section className="panel">
        <h2>Attendees</h2>
        <EventAttendeeList data={attendeeData} />
      </section>
    </div>
  );
}
