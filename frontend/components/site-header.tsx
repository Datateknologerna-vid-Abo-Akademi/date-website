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
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="site-header__brand">
          {associationName}
        </Link>
        <nav className="site-header__nav" aria-label="Main navigation">
          <Link href="/">Home</Link>
          <Link href="/news">News</Link>
          <Link href="/events">Events</Link>
          {showPolls ? <Link href="/polls">Polls</Link> : null}
          <Link href="/members">Members</Link>
          <Link href="/archive">Archive</Link>
          <Link href="/social">Social</Link>
          <Link href="/ads">Ads</Link>
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
