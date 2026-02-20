/* eslint-disable @next/next/no-img-element */
import Link from "next/link";

import type { HomePayload } from "@/lib/api/types";

import { formatDate, toPreviewText } from "./utils";
import styles from "./home-news-feed.module.css";

interface HomeNewsFeedProps {
  homeData: HomePayload;
  showNews: boolean;
  showNewsLinkHeading: boolean;
  showAaIcon: boolean;
  aaPostHref: string;
}

export function HomeNewsFeed({
  homeData,
  showNews,
  showNewsLinkHeading,
  showAaIcon,
  aaPostHref,
}: HomeNewsFeedProps) {
  if (!showNews) return null;

  return (
    <div className={`feed-container ${styles.feedContainer}`}>
      <h3
        className={`news-header header-border-bottom mt-3 ${styles.newsHeader}${
          showNewsLinkHeading ? " heading-link" : ""
        }`}
      >
        {showNewsLinkHeading ? <Link href="/news">Nyheter</Link> : "Nyheter"}
        {showAaIcon ? (
          <span className={`aa-img ${styles.aaIcon}`}>
            <Link href={aaPostHref}>
              <img src="/static/core/images/albins-angels.png" alt="Albins Angels" />
            </Link>
          </span>
        ) : null}
      </h3>
      <div className={`news-container ${styles.newsContainer}`}>
        {homeData.news.length > 0 ? (
          homeData.news.map((item) => (
            <div
              key={item.slug}
              className={`news-content news-box header-border-bottom ${styles.newsContent} ${styles.newsBox}`}
            >
              <h3 className="news-title">{item.title}</h3>
              <h5 className={`news-date ${styles.newsDate}`}>{formatDate(item.published_time)}</h5>
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
  );
}
