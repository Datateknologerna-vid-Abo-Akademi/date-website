import Link from "next/link";

import { getEvents } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function EventsPage() {
  await ensureModuleEnabled("events");
  const events = await getEvents(true);
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Events</p>
        <h1>All Events</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {events.map((event) => (
            <li key={event.slug}>
              <h2>
                <Link href={`/events/${event.slug}`}>{event.title}</Link>
              </h2>
              <p className="meta">
                {new Date(event.event_date_start).toLocaleString()} -{" "}
                {new Date(event.event_date_end).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
