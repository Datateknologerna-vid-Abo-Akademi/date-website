import { notFound } from "next/navigation";

import { RichContent } from "@/components/rich-content";
import { getEvent } from "@/lib/api/queries";

interface EventDetailPageProps {
  params: {
    slug: string;
  };
}

export default async function EventDetailPage({ params }: EventDetailPageProps) {
  const { slug } = params;
  const event = await getEvent(slug).catch(() => null);
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
    </div>
  );
}
