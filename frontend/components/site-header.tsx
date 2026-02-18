import Link from "next/link";

import type { SiteMeta } from "@/lib/api/types";

interface SiteHeaderProps {
  siteMeta: SiteMeta;
}

export function SiteHeader({ siteMeta }: SiteHeaderProps) {
  const associationName =
    (siteMeta.content_variables.ASSOCIATION_NAME_SHORT as string | undefined) ?? "Association";
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
          <Link href="/polls">Polls</Link>
          <Link href="/members">Members</Link>
          <Link href="/archive">Archive</Link>
          <Link href="/publications">Publications</Link>
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
