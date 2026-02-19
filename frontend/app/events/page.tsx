import Link from "next/link";

import { getEvents } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

const LEGACY_TIME_ZONE = "Europe/Helsinki";

function toPreviewText(value: string, maxWords = 20) {
  const plain = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (!plain) return "";
  const words = plain.split(" ");
  if (words.length <= maxWords) return plain;
  return `${words.slice(0, maxWords).join(" ")}...`;
}

function formatDatePart(value: string, options: Intl.DateTimeFormatOptions) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("sv-FI", {
    ...options,
    timeZone: LEGACY_TIME_ZONE,
  }).format(date);
}

function formatDay(value: string) {
  return formatDatePart(value, { day: "2-digit" });
}

function formatMonth(value: string) {
  return formatDatePart(value, { month: "short" });
}

function formatTime(value: string) {
  return formatDatePart(value, { hour: "2-digit", minute: "2-digit" });
}

function formatWeekday(value: string) {
  return formatDatePart(value, { weekday: "short" });
}

function formatParticipants(maxParticipants: number) {
  if (maxParticipants === 0) return "Ingen begransning";
  return String(maxParticipants);
}

export default async function EventsPage() {
  await ensureModuleEnabled("events");
  const [upcomingEvents, allEvents] = await Promise.all([
    getEvents(false),
    getEvents(true),
  ]);
  const upcomingEventSlugs = new Set(upcomingEvents.map((event) => event.slug));
  const pastEvents = allEvents
    .filter((event) => !upcomingEventSlugs.has(event.slug))
    .sort((left, right) => new Date(right.event_date_start).getTime() - new Date(left.event_date_start).getTime());

  return (
    <div className="events-index-page container-md min-vh-100 container-margin-top">
      <div className="container-size break-words">
        <div className="row">
          <div className="col-md-12">
            <h2 className="text-center">
              <span>Kommande handelser</span>
            </h2>
            {upcomingEvents.length > 0 ? (
              upcomingEvents.map((event) => (
                <div key={event.slug} className="card-group event-card text-light mb-2">
                  <div className="card mb-0 p-1">
                    <div className="card-body py-1">
                      <div className="row">
                        <div className="col-4 col-sm-2 m-auto">
                          <div className="display-4">
                            <span className="badge">{formatDay(event.event_date_start)}</span>
                          </div>
                          <div className="display-4 event-date-txt">{formatMonth(event.event_date_start)}</div>
                        </div>
                        <div className="col-8 col-sm-6">
                          <div className="d-flex flex-column">
                            <h3 className="card-title text-uppercase mt-0">
                              <strong>{event.title}</strong>
                            </h3>
                            <div className="card-text">{toPreviewText(event.content)}</div>
                          </div>
                        </div>
                        <div className="col-6 col-sm-2 m-auto">
                          <ul className="list-group my-0 pl-1">
                            <li className="list-inline-item">
                              <i className="far fa-clock" /> {formatTime(event.event_date_start)} -{" "}
                              {formatTime(event.event_date_end)}
                            </li>
                            <li className="list-inline-item">
                              <i className="fas fa-calendar-check" /> {formatWeekday(event.event_date_start)}
                            </li>
                            <li className="list-inline-item">
                              <i className="fas fa-users" /> {formatParticipants(event.sign_up_max_participants)}
                            </li>
                          </ul>
                        </div>
                        <div className="col-6 col-sm-2 text-center m-auto">
                          {event.redirect_link ? (
                            <a
                              className="btn btn-outline-light btn-floating m-1"
                              href={event.redirect_link}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <i className="fas fa-chevron-right fa-4x" />
                            </a>
                          ) : (
                            <Link className="btn btn-outline-light btn-floating m-1" href={`/events/${event.slug}`}>
                              <i className="fas fa-chevron-right fa-4x" />
                            </Link>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <h5 className="text-center">Inga aktiva handelser</h5>
            )}
          </div>
          <div className="text-center mt-5 events-index-past">
            <h2>
              <span>Tidigare handelser</span>
            </h2>
            {pastEvents.slice(0, 5).map((event) => (
              <div key={event.slug}>
                <Link className="content-past" href={`/events/${event.slug}`}>
                  <h4 className="event-title-ended">{event.title}</h4>
                </Link>
              </div>
            ))}
            {pastEvents.length === 0 ? <h5>Inga tidigare handelser</h5> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
