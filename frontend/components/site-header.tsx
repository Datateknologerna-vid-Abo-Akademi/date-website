import Link from "next/link";

import type { SiteMeta } from "@/lib/api/types";
import { getModuleNavigation } from "@/lib/modules";

interface SiteHeaderProps {
  siteMeta: SiteMeta;
}

export function SiteHeader({ siteMeta }: SiteHeaderProps) {
  const associationName =
    (siteMeta.content_variables.ASSOCIATION_NAME_SHORT as string | undefined) ?? "Association";
  const moduleNav = getModuleNavigation(siteMeta);
  const showHome = siteMeta.default_landing_path === "/";

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="site-header__brand">
          {associationName}
        </Link>
        <nav className="site-header__nav" aria-label="Main navigation">
          {showHome ? <Link href="/">Home</Link> : null}
          <Link href="/members">Members</Link>
          {moduleNav.map((item) => (
            <Link key={item.moduleKey} href={item.href}>
              {item.label}
            </Link>
          ))}
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
