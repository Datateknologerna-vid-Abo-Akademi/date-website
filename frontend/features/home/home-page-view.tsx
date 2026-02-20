/* eslint-disable @next/next/no-img-element */
import Link from "next/link";

import { HomeJoke } from "@/components/home/home-joke";
import type { HomePayload } from "@/lib/api/types";

import { HomeHero } from "./home-hero";
import { HomeNewsFeed } from "./home-news-feed";
import { LegacyEventSection, LegacyPartnerCarousel } from "./legacy-sections";
import styles from "./home-page-view.module.css";

interface HomePageViewProps {
  homeData: HomePayload;
  brand: string;
  associationName: string;
  heroSubtitle: string;
  heroLogo: string;
  inlineHeroLogo: string;
  aboutText: string;
  showNews: boolean;
  showEvents: boolean;
}

export function HomePageView({
  homeData,
  brand,
  associationName,
  heroSubtitle,
  heroLogo,
  inlineHeroLogo,
  aboutText,
  showNews,
  showEvents,
}: HomePageViewProps) {
  const isDateLikeBrand = brand === "date" || brand === "demo";
  const isKkBrand = brand === "kk";
  const isBiocumBrand = brand === "biocum";
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
  const rootClassName = [
    styles.root,
    `home-page home-page--${brand || "default"}`,
    isKkBrand ? styles.brandKk : "",
    isBiocumBrand ? styles.brandBiocum : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClassName}>
      <div className={styles.shell}>
        <HomeHero
          brand={brand}
          associationName={associationName}
          heroSubtitle={heroSubtitle}
          heroLogo={heroLogo}
          inlineHeroLogo={inlineHeroLogo}
        />

        {aboutText ? (
          <section className={`about ${styles.about}`}>
            <div className={`container-size ${styles.containerSize}`}>
              <h3>Om oss</h3>
              <p>{aboutText}</p>
            </div>
          </section>
        ) : null}

        <section id="news" className={`news-events ${styles.newsEvents}`}>
          <div id="main" className={`main-container ${styles.mainContainer}`}>
            <HomeNewsFeed
              homeData={homeData}
              showNews={showNews}
              showNewsLinkHeading={showNewsLinkHeading}
              showAaIcon={showAaIcon}
              aaPostHref={aaPostHref}
            />

            {isBiocumBrand ? (
              <>
                <div className={`sidebar-container ${styles.sidebarContainer}`}>
                  {showEvents ? (
                    <LegacyEventSection
                      events={homeData.events}
                      calendarEvents={homeData.calendar_events}
                      linkedHeading={showEventLinkHeading}
                    />
                  ) : null}
                  {partnerAds.length > 0 ? (
                    <LegacyPartnerCarousel ads={partnerAds} mobile={false} />
                  ) : null}
                </div>
                <div className={`mobile-blocks ${styles.mobileBlocks}`}>
                  {showEvents ? (
                    <LegacyEventSection
                      className={`mobile-events-container ${styles.mobileEventsContainer}`}
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
                  <div className={`extra-container ${styles.extraContainer}`}>
                    <h3 className="mt-3 header-border-bottom">Annat</h3>
                    <h5 className="heading-link">
                      <Link href="/social/harassment">Trakasseriombud</Link>
                    </h5>
                    <p>
                      Om du upplever trakasserier i samband med Datateknologernas verksamhet,
                      vänligen <Link href="/social/harassment/">rapportera</Link> detta via hemsidan.
                      Vi tar alla former av trakasserier på allvar och kommer att vidta åtgärder för
                      att upprätthålla en trygg och respektfull miljö för alla medlemmar.
                    </p>
                    <HomeJoke />
                  </div>
                ) : null}

                {isDateLikeBrand ? (
                  <div
                    className={`logo-container ${styles.logoContainer} ${isDateLikeBrand ? styles.logoContainerDateDemo : ""}`}
                  >
                    <h3 className="header-border-bottom">Samarbetspartners</h3>
                    <div className="d-flex flex-wrap justify-content-center align-items-center">
                      {partnerAds.map((ad, index) =>
                        ad.company_url ? (
                          <a
                            key={`${ad.ad_url}-${index}`}
                            className="m-2"
                            href={ad.company_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <img src={ad.ad_url} alt="img" />
                          </a>
                        ) : (
                          <span key={`${ad.ad_url}-${index}`} className="m-2 d-inline-block">
                            <img src={ad.ad_url} alt="img" />
                          </span>
                        ),
                      )}
                    </div>
                    <div className="text-center">
                      <Link href="/pages/foretagssamarbete/">Vill du samarbeta med DaTe?</Link>
                    </div>
                  </div>
                ) : partnerAds.length > 0 ? (
                  <LegacyPartnerCarousel ads={partnerAds} mobile={false} />
                ) : null}

                {showInstagram ? (
                  <div className={`ig-scroll ${styles.igScroll}`}>
                    <div className={`scroll-content ${styles.scrollContent}`}>
                      <div className="slideshow">
                        <div className={`images ${styles.images}`}>
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

        <section id="reklam" className={`text-size ${styles.textSize}`} />
      </div>
    </div>
  );
}
