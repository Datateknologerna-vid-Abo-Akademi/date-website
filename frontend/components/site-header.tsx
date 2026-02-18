import Link from "next/link";

import type { SiteMeta } from "@/lib/api/types";

interface SiteHeaderProps {
  siteMeta: SiteMeta;
}

export function SiteHeader({ siteMeta }: SiteHeaderProps) {
  const associationName =
    (siteMeta.content_variables.ASSOCIATION_NAME_SHORT as string | undefined) ?? "Association";
  const enabledModules = new Set(siteMeta.enabled_modules ?? []);
  const showPolls = enabledModules.has("polls");
  const showPublications = enabledModules.has("publications");
  const showCtf = enabledModules.has("ctf");
  const showLucia = enabledModules.has("lucia");
  const showAlumni = enabledModules.has("alumni");
  const showNews = enabledModules.has("news");
  const showEvents = enabledModules.has("events");
  const showArchive = enabledModules.has("archive");
  const showSocial = enabledModules.has("social");
  const showAds = enabledModules.has("ads");
  const showHome = siteMeta.default_landing_path === "/";
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="site-header__brand">
          {associationName}
        </Link>
        <nav className="site-header__nav" aria-label="Main navigation">
          {showHome ? <Link href="/">Home</Link> : null}
          {showNews ? <Link href="/news">News</Link> : null}
          {showEvents ? <Link href="/events">Events</Link> : null}
          {showPolls ? <Link href="/polls">Polls</Link> : null}
          <Link href="/members">Members</Link>
          {showArchive ? <Link href="/archive">Archive</Link> : null}
          {showSocial ? <Link href="/social">Social</Link> : null}
          {showAds ? <Link href="/ads">Ads</Link> : null}
          {showPublications ? <Link href="/publications">Publications</Link> : null}
          {showCtf ? <Link href="/ctf">CTF</Link> : null}
          {showLucia ? <Link href="/lucia">Lucia</Link> : null}
          {showAlumni ? <Link href="/alumni/signup">Alumni</Link> : null}
          {siteMeta.navigation.slice(0, 3).map((navCategory) =>
            navCategory.url ? (
              <a key={navCategory.category_name} href={navCategory.url}>
                {navCategory.category_name}
              </a>
            ) : null,
          )}
        </nav>
      </div>
    </header>
  );
}
