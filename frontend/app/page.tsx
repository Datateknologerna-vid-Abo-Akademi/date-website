/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { redirect } from "next/navigation";

import { HomeCalendar } from "@/components/home/home-calendar";
import { HomeJoke } from "@/components/home/home-joke";
import { getHomeData, getSiteMeta } from "@/lib/api/queries";
import { BIOCUM_HERO_LOGO_SVG, DATE_HERO_LOGO_SVG, KK_HERO_LOGO_SVG } from "@/lib/legacy-hero-logos";
import { isModuleEnabled } from "@/lib/modules";
import type { AdItem, EventItem } from "@/lib/api/types";

const LEGACY_TIME_ZONE = "Europe/Helsinki";

function formatLegacyDatePart(value: string | null, options: Intl.DateTimeFormatOptions) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("sv-FI", {
    ...options,
    timeZone: LEGACY_TIME_ZONE,
  }).format(date);
}

function formatDate(value: string | null) {
  return formatLegacyDatePart(value, { day: "2-digit", month: "short", year: "numeric" });
}

function formatDay(value: string | null) {
  return formatLegacyDatePart(value, { day: "2-digit" });
}

function formatMonth(value: string | null) {
  return formatLegacyDatePart(value, { month: "short" });
}

function formatWeekday(value: string | null) {
  return formatLegacyDatePart(value, { weekday: "short" });
}

function formatTime(value: string | null) {
  return formatLegacyDatePart(value, { hour: "2-digit", minute: "2-digit" });
}

function getTagline(associationName: string, associationFullName: string) {
  if (!associationFullName) return "";
  const prefixPattern = new RegExp(`^${associationName}\\s*`, "i");
  const tagline = associationFullName.replace(prefixPattern, "").trim();
  return tagline || associationFullName;
}

function getHeroSubtitle(brand: string, associationName: string, associationFullName: string) {
  if (brand === "biocum") {
    return "vid Åbo Akademi";
  }
  return getTagline(associationName, associationFullName);
}

function toPreviewText(value: string, maxWords = 28) {
  const plain = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (!plain) return "";
  const words = plain.split(" ");
  if (words.length <= maxWords) return plain;
  return `${words.slice(0, maxWords).join(" ")}...`;
}

function getHeroLogoSrc() {
  return "/static/core/images/headerlogo.png";
}

const INLINE_HERO_LOGOS: Record<string, string> = {
  date: DATE_HERO_LOGO_SVG,
  demo: DATE_HERO_LOGO_SVG,
  kk: KK_HERO_LOGO_SVG,
  biocum: BIOCUM_HERO_LOGO_SVG,
};

function getAboutText(brand: string) {
  if (brand === "date") {
    return "Datateknologerna vid Åbo Akademi rf är en förening för studerande vid utbildningsprogrammet i datateknik vid Fakulteten för Naturvetenskaper och Teknik vid Åbo Akademi, samt för studerande vid övriga tekniskt inriktade utbildningslinjer i databehandling. Föreningen grundades 1999, närmare bestämt den 24.8 kl. 16:32. Medlemmarna känns igen på deras svarta halare och stiliga tofsmössor.";
  }
  if (brand === "demo") {
    return "DaTe demo website, contact datedatorer@gmail.com if you have questions.";
  }
  return "";
}

interface LegacyEventSectionProps {
  events: EventItem[];
  calendarEvents: Record<
    string,
    {
      link: string;
      modifier: string;
      eventFullDate: string;
      eventTitle: string;
    }
  >;
  linkedHeading: boolean;
  className?: string;
}

function LegacyEventSection({ events, calendarEvents, linkedHeading, className = "events-container" }: LegacyEventSectionProps) {
  return (
    <div className={className}>
      <h3 className={`header-border-bottom mt-3${linkedHeading ? " heading-link" : ""}`}>
        {linkedHeading ? <Link href="/events">Evenemang</Link> : "Evenemang"}
      </h3>
      <HomeCalendar events={calendarEvents} />
      <div className="events">
        <div className="row">
          <div className="col-md-12">
            {events.slice(0, 4).map((item) => (
              <div key={item.slug} className="card-group event-card text-light mb-2">
                <Link href={`/events/${item.slug}`} className="card mb-0 p-1">
                  <div className="card-body py-1">
                    <div className="row">
                      <div className="col-3 m-auto">
                        <div>
                          <span className="badge">{formatDay(item.event_date_start)}</span>
                        </div>
                        <div className="text-color">
                          {formatMonth(item.event_date_start)}
                        </div>
                      </div>
                      <div className="col-7 m-auto">
                        <div className="d-flex flex-column">
                          <small className="list-inline-item">
                            <i className="fas fa-calendar-check" /> {formatWeekday(item.event_date_start)}
                            {" "}
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
              <Link className="more-events-button" href="/events">
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

function LegacyPartnerCarousel({ ads, mobile }: LegacyPartnerCarouselProps) {
  const doubledAds = ads.length > 1 ? [...ads, ...ads] : ads;
  return (
    <div className={mobile ? "mobile-logo-container" : "logo-container"}>
      <h3 className={mobile ? "" : "mt-3"}>Samarbetspartners</h3>
      <div className={`carousel-logos${mobile ? " text-center" : ""}`}>
        <ul className="logo-carousel-track">
          {doubledAds.map((ad, index) => (
            <li key={`${ad.ad_url}-${index}`} className="company-logo text-center" aria-hidden={index >= ads.length}>
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

export default async function Home() {
  const siteMeta = await getSiteMeta();
  if (siteMeta.default_landing_path && siteMeta.default_landing_path !== "/") {
    redirect(siteMeta.default_landing_path);
  }

  const homeData = await getHomeData();
  const showNews = isModuleEnabled(siteMeta, "news");
  const showEvents = isModuleEnabled(siteMeta, "events");
  const associationName =
    (siteMeta.content_variables.ASSOCIATION_NAME as string | undefined) ?? "Association";
  const associationFullName =
    (siteMeta.content_variables.ASSOCIATION_NAME_FULL as string | undefined) ?? "";
  const brand = (siteMeta.association_theme.brand ?? "").toLowerCase();
  const isDateLikeBrand = brand === "date" || brand === "demo";
  const isKkBrand = brand === "kk";
  const isBiocumBrand = brand === "biocum";
  const aboutText = getAboutText(brand);
  const heroSubtitle = getHeroSubtitle(brand, associationName, associationFullName);
  const heroLogo = getHeroLogoSrc();
  const inlineHeroLogo = INLINE_HERO_LOGOS[brand] || "";
  const partnerAds = homeData.ads.filter((ad) => Boolean(ad.ad_url));
  const showExtraPanel = isDateLikeBrand;
  const showInstagram = isKkBrand && homeData.instagram_posts.length > 0;
  const aaPostHref = homeData.aa_post
    ? homeData.aa_post.category_slug
      ? `/news/${homeData.aa_post.category_slug}/${homeData.aa_post.slug}`
      : `/news/articles/${homeData.aa_post.slug}`
    : "";
  const showAaIcon = isDateLikeBrand && Boolean(homeData.aa_post);
  const showNewsLinkHeading = !isBiocumBrand;
  const showEventLinkHeading = !isBiocumBrand;

  return (
    <div className={`home-page home-page--${brand || "default"}`}>
      <div className="container-fluid p-2 min-vh-100">
        {isBiocumBrand ? (
          <header className="header wave home-hero-legacy">
            <div className="scaling-svg-container home-hero-logo-wrap">
              {inlineHeroLogo ? (
                <div
                  className="home-hero-logo-inline home-hero-logo-inline--animated"
                  aria-hidden="true"
                  dangerouslySetInnerHTML={{ __html: inlineHeroLogo }}
                />
              ) : (
                <img src={heroLogo} alt={associationName} className="home-hero-logo home-hero-logo--animated" />
              )}
            </div>
            <div className="text">
              <h1 className="hero-text-main">{associationName}</h1>
              {heroSubtitle ? <h3 className="hero-text-sub">{heroSubtitle}</h3> : null}
            </div>
          </header>
        ) : (
          <header className="header home-hero-legacy">
            <div className="hero-text-box">
              <div className={isKkBrand ? "scaling-svg-container home-hero-logo-wrap" : "albin home-hero-logo-wrap"}>
                {inlineHeroLogo ? (
                  <div
                    className="home-hero-logo-inline home-hero-logo-inline--animated"
                    aria-hidden="true"
                    dangerouslySetInnerHTML={{ __html: inlineHeroLogo }}
                  />
                ) : (
                  <img src={heroLogo} alt={associationName} className="home-hero-logo home-hero-logo--animated" />
                )}
              </div>
              <div className="text">
                <h1>{associationName}</h1>
                {heroSubtitle ? <h3>{heroSubtitle}</h3> : null}
              </div>
            </div>
          </header>
        )}

        {aboutText ? (
          <section className="about">
            <div className="container-size">
              <h3>Om oss</h3>
              <p>{aboutText}</p>
            </div>
          </section>
        ) : null}

        <section id="news" className="news-events">
          <div id="main" className="main-container">
            {showNews ? (
              <div className="feed-container">
                <h3 className={`news-header header-border-bottom mt-3${showNewsLinkHeading ? " heading-link" : ""}`}>
                  {showNewsLinkHeading ? <Link href="/news">Nyheter</Link> : "Nyheter"}
                  {showAaIcon ? (
                    <span className="aa-img">
                      <Link href={aaPostHref}>
                        <img src="/static/core/images/albins-angels.png" alt="Albins Angels" />
                      </Link>
                    </span>
                  ) : null}
                </h3>
                <div className="news-container">
                  {homeData.news.length > 0 ? (
                    homeData.news.map((item) => (
                      <div key={item.slug} className="news-content news-box header-border-bottom">
                        <h3 className="news-title">{item.title}</h3>
                        <h5 className="news-date">{formatDate(item.published_time)}</h5>
                        <div className="news-preview">{toPreviewText(item.content, 50)}</div>
                        <Link className="news-button" href={`/news/articles/${item.slug}`}>
                          <i className="fab fa-readme" /> Läs mera...
                        </Link>
                      </div>
                    ))
                  ) : (
                    <h3>Inga nyheter hittades...</h3>
                  )}
                  <Link className="more-news" href="/news">
                    <i className="far fa-newspaper" /> Mera nyheter...
                  </Link>
                </div>
              </div>
            ) : null}

            {isBiocumBrand ? (
              <>
                <div className="sidebar-container">
                  {showEvents ? (
                    <LegacyEventSection
                      events={homeData.events}
                      calendarEvents={homeData.calendar_events}
                      linkedHeading={showEventLinkHeading}
                    />
                  ) : null}
                  {partnerAds.length > 0 ? <LegacyPartnerCarousel ads={partnerAds} mobile={false} /> : null}
                </div>
                <div className="mobile-blocks">
                  {showEvents ? (
                    <LegacyEventSection
                      className="mobile-events-container"
                      events={homeData.events}
                      calendarEvents={homeData.calendar_events}
                      linkedHeading={showEventLinkHeading}
                    />
                  ) : null}
                  {partnerAds.length > 0 ? <LegacyPartnerCarousel ads={partnerAds} mobile /> : null}
                </div>
              </>
            ) : (
              <>
                {showEvents ? (
                  <LegacyEventSection
                    events={homeData.events}
                    calendarEvents={homeData.calendar_events}
                    linkedHeading={showEventLinkHeading}
                  />
                ) : null}

                {showExtraPanel ? (
                  <div className="extra-container">
                    <h3 className="mt-3 header-border-bottom">Annat</h3>
                    <h5 className="heading-link">
                      <Link href="/social/harassment">Trakasseriombud</Link>
                    </h5>
                    <p>
                      Om du upplever trakasserier i samband med Datateknologernas verksamhet, vänligen{" "}
                      <Link href="/social/harassment/">rapportera</Link> detta via hemsidan. Vi tar alla former av trakasserier
                      på allvar och kommer att vidta åtgärder för att upprätthålla en trygg och respektfull miljö för alla
                      medlemmar.
                    </p>
                    <HomeJoke />
                  </div>
                ) : null}

                {isDateLikeBrand ? (
                  <div className="logo-container">
                    <h3 className="header-border-bottom">Samarbetspartners</h3>
                    <div className="d-flex flex-wrap justify-content-center align-items-center">
                      {partnerAds.map((ad, index) => (
                        ad.company_url ? (
                          <a key={`${ad.ad_url}-${index}`} className="m-2" href={ad.company_url} target="_blank" rel="noreferrer">
                            <img src={ad.ad_url} alt="img" />
                          </a>
                        ) : (
                          <span key={`${ad.ad_url}-${index}`} className="m-2 d-inline-block">
                            <img src={ad.ad_url} alt="img" />
                          </span>
                        )
                      ))}
                    </div>
                    <div className="text-center">
                      <Link href="/pages/foretagssamarbete/">Vill du samarbeta med DaTe?</Link>
                    </div>
                  </div>
                ) : partnerAds.length > 0 ? (
                  <LegacyPartnerCarousel ads={partnerAds} mobile={false} />
                ) : null}

                {showInstagram ? (
                  <div className="ig-scroll">
                    <div className="scroll-content">
                      <div className="slideshow">
                        <div className="images">
                          {homeData.instagram_posts.map((post) => (
                            <a
                              key={post.shortcode}
                              href={`https://www.instagram.com/p/${post.shortcode}/`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <img src={post.url} alt="image" />
                            </a>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </section>

        <section id="reklam" className="text-size" />
      </div>
    </div>
  );
}
