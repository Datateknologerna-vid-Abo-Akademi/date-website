import Link from "next/link";
import { redirect } from "next/navigation";

import { RichContent } from "@/components/rich-content";
import { getHomeData, getSiteMeta } from "@/lib/api/queries";
import { isModuleEnabled } from "@/lib/modules";

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
  return (
    <div className="page-shell">
      <section className="hero">
        <p className="eyebrow">Decoupled Portal</p>
        <h1>{associationName}</h1>
        <p>
          This frontend is now API-driven and association-aware, with runtime theme configuration
          from Django.
        </p>
      </section>

      {showNews || showEvents ? (
        <section className="content-grid">
          {showNews ? (
            <article className="panel">
              <h2>Latest News</h2>
              <ul className="list">
                {homeData.news.map((item) => (
                  <li key={item.slug}>
                    <Link href={`/news/articles/${item.slug}`}>{item.title}</Link>
                  </li>
                ))}
              </ul>
              <Link href="/news" className="cta-link">
                Browse all news
              </Link>
            </article>
          ) : null}

          {showEvents ? (
            <article className="panel">
              <h2>Upcoming Events</h2>
              <ul className="list">
                {homeData.events.map((item) => (
                  <li key={item.slug}>
                    <Link href={`/events/${item.slug}`}>{item.title}</Link>
                  </li>
                ))}
              </ul>
              <Link href="/events" className="cta-link">
                Browse all events
              </Link>
            </article>
          ) : null}
        </section>
      ) : null}

      {homeData.aa_post ? (
        <section className="panel highlight">
          <h2>{homeData.aa_post.title}</h2>
          <RichContent html={homeData.aa_post.content} />
        </section>
      ) : null}
    </div>
  );
}
