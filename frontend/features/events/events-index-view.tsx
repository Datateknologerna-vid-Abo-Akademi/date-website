import Link from "next/link";

import type { EventItem } from "@/lib/api/types";

import {
  formatDay,
  formatMonth,
  formatParticipants,
  formatTime,
  formatWeekday,
  toPreviewText,
} from "./events-utils";
import styles from "./events-index-view.module.css";

interface EventsIndexViewProps {
  upcomingEvents: EventItem[];
  pastEvents: EventItem[];
  isON: boolean;
}

export function EventsIndexView({ upcomingEvents, pastEvents, isON }: EventsIndexViewProps) {
  return (
    <div
      className={`events-index-page ${styles.root} ${isON ? "event-variant--on-index" : "container-md min-vh-100 container-margin-top"}`}
    >
      <div className={`${isON ? "container-md min-vh-100" : ""}`}>
        <div className={`container-size break-words ${isON ? "container-margin-top pt-12" : ""}`}>
          <div className="row">
            <div className="col-md-12">
              <h2 className="text-center">
                <span>Kommande händelser</span>
              </h2>
              {upcomingEvents.length > 0 ? (
                upcomingEvents.map((event) => (
                  <div
                    key={event.slug}
                    className={`card-group event-card text-light mb-2 ${styles.eventCard} ${isON ? "on-event-card" : ""}`}
                  >
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
                <h5 className="text-center">Inga aktiva händelser</h5>
              )}
            </div>
            <div className="text-center mt-5 events-index-past">
              <h2>
                <span>Tidigare händelser</span>
              </h2>
              {pastEvents.slice(0, 5).map((event) => (
                <div key={event.slug}>
                  <Link className={`content-past ${styles.contentPast}`} href={`/events/${event.slug}`}>
                    <h4 className="event-title-ended">{event.title}</h4>
                  </Link>
                </div>
              ))}
              {pastEvents.length === 0 ? <h5>Inga tidigare händelser</h5> : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
