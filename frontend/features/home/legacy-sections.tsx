/* eslint-disable @next/next/no-img-element */
import Link from "next/link";

import { HomeCalendar } from "@/components/home/home-calendar";
import type { AdItem, EventItem, HomePayload } from "@/lib/api/types";

import { formatDay, formatMonth, formatTime, formatWeekday } from "./utils";
import styles from "./legacy-sections.module.css";

interface LegacyEventSectionProps {
  events: EventItem[];
  calendarEvents: HomePayload["calendar_events"];
  linkedHeading: boolean;
  className?: string;
}

export function LegacyEventSection({
  events,
  calendarEvents,
  linkedHeading,
  className,
}: LegacyEventSectionProps) {
  const containerClassName = className
    ? `${styles.eventsContainer} ${className}`
    : `${styles.eventsContainer} events-container`;

  return (
    <div className={containerClassName}>
      <h3 className={`header-border-bottom mt-3${linkedHeading ? " heading-link" : ""}`}>
        {linkedHeading ? <Link href="/events">Evenemang</Link> : "Evenemang"}
      </h3>
      <HomeCalendar events={calendarEvents} />
      <div className={`${styles.events} events`}>
        <div className="row">
          <div className="col-md-12">
            {events.slice(0, 4).map((item) => (
              <div
                key={item.slug}
                className={`card-group event-card text-light mb-2 ${styles.eventCard}`}
              >
                <Link href={`/events/${item.slug}`} className="card mb-0 p-1">
                  <div className="card-body py-1">
                    <div className="row">
                      <div className="col-3 m-auto">
                        <div>
                          <span className="badge">{formatDay(item.event_date_start)}</span>
                        </div>
                        <div className={`text-color ${styles.textColor}`}>
                          {formatMonth(item.event_date_start)}
                        </div>
                      </div>
                      <div className="col-7 m-auto">
                        <div className="d-flex flex-column">
                          <small className="list-inline-item">
                            <i className="fas fa-calendar-check" /> {formatWeekday(item.event_date_start)}{" "}
                            <i className="far fa-clock" /> {formatTime(item.event_date_start)}
                          </small>
                          <h6 className="card-title text-uppercase mt-0">
                            <strong>{item.title}</strong>
                          </h6>
                        </div>
                      </div>
                      <div className="col-2 m-auto">
                        <i className="fas fa-chevron-right fa-lg" />
                      </div>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
            {events.length === 0 ? <h6>Inga aktiva evenemang hittades...</h6> : null}
            {events.length >= 4 ? (
              <Link className={`more-events-button ${styles.moreEventsButton}`} href="/events">
                <i className="far fa-calendar-alt" /> Mera evenemang...
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

interface LegacyPartnerCarouselProps {
  ads: AdItem[];
  mobile: boolean;
}

export function LegacyPartnerCarousel({ ads, mobile }: LegacyPartnerCarouselProps) {
  const doubledAds = ads.length > 1 ? [...ads, ...ads] : ads;

  return (
    <div
      className={
        mobile
          ? `${styles.mobileLogoContainer} mobile-logo-container`
          : `${styles.logoContainer} logo-container`
      }
    >
      <h3 className={mobile ? "" : "mt-3"}>Samarbetspartners</h3>
      <div className={`${styles.carouselLogos} carousel-logos${mobile ? " text-center" : ""}`}>
        <ul className={`${styles.logoCarouselTrack} logo-carousel-track`}>
          {doubledAds.map((ad, index) => (
            <li
              key={`${ad.ad_url}-${index}`}
              className={`${styles.companyLogo} company-logo text-center`}
              aria-hidden={index >= ads.length}
            >
              {ad.company_url ? (
                <a href={ad.company_url} target="_blank" rel="noreferrer">
                  <img src={ad.ad_url} alt="img" />
                </a>
              ) : (
                <img src={ad.ad_url} alt="img" />
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
