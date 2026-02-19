/* eslint-disable @next/next/no-img-element */
import Link from "next/link";

import { LogoutButton } from "@/components/members/logout-button";
import type { SessionData, SiteMeta } from "@/lib/api/types";
import { getModuleNavigation } from "@/lib/modules";

interface SiteHeaderProps {
  siteMeta: SiteMeta;
  session: SessionData;
}

function isInternalRoute(url: string) {
  return url.startsWith("/") && !url.startsWith("//");
}

function isLoginRoute(url: string) {
  return url === "/members/login" || url === "/members/login/";
}

function renderNavLink(url: string, label: string, className = "nav-link") {
  if (isInternalRoute(url)) {
    return (
      <Link href={url} className={className}>
        {label}
      </Link>
    );
  }
  return (
    <a href={url} className={className} target="_blank" rel="noreferrer">
      {label}
    </a>
  );
}

export function SiteHeader({ siteMeta, session }: SiteHeaderProps) {
  const associationName =
    (siteMeta.content_variables.ASSOCIATION_NAME as string | undefined) ?? "Association";
  const associationShortName =
    (siteMeta.content_variables.ASSOCIATION_NAME_SHORT as string | undefined) ?? associationName;
  const moduleNav = getModuleNavigation(siteMeta);
  const navCategories = [...siteMeta.navigation].sort(
    (left, right) => left.nav_element - right.nav_element,
  );
  const staticPagesEnabled = siteMeta.module_capabilities.staticpages?.enabled ?? false;
  const hasAdminNavigation = navCategories.length > 0;
  const showFallbackNav = !hasAdminNavigation && !staticPagesEnabled;
  const showHome = siteMeta.default_landing_path === "/";
  const homeHref = showHome ? "/" : siteMeta.default_landing_path || "/";

  return (
    <header className="site-header legacy-site-header">
      <nav className="navbar navbar-expand-lg navbar-light fixed-top legacy-navbar">
        <div className="container">
          <Link id="logo" href={homeHref} className="navbar-brand">
            <img
              src="/static/core/images/headerlogo.png"
              alt={associationShortName}
              className="header-logo"
            />
          </Link>
          <button
            className="btn btn-secondary navbar-toggler border-3 px-2 legacy-nav-toggler"
            type="button"
            data-bs-toggle="offcanvas"
            data-bs-target="#legacyNavOffcanvas"
            aria-controls="legacyNavOffcanvas"
            aria-label="Open navigation"
          >
            <i className="bi bi-list fa-2x" />
          </button>
          <div
            className="offcanvas offcanvas-start-lg"
            tabIndex={-1}
            id="legacyNavOffcanvas"
            aria-labelledby="legacyNavOffcanvasLabel"
          >
            <div className="offcanvas-header d-flex d-lg-none">
              <h5 className="offcanvas-title text-white" id="legacyNavOffcanvasLabel">
                {associationShortName}
              </h5>
              <button
                type="button"
                className="btn-close btn-close-white"
                data-bs-dismiss="offcanvas"
                aria-label="Close"
              />
            </div>
            <div className="offcanvas-body p-lg-0 justify-content-end">
              <ul className="navbar-nav">
                {hasAdminNavigation
                  ? navCategories.map((category) => {
                      if (category.use_category_url && category.url) {
                        const key = `${category.category_name}-${category.nav_element}-${category.url}`;
                        return (
                          <li key={key} className="nav-item">
                            {renderNavLink(category.url, category.category_name)}
                          </li>
                        );
                      }

                      const categoryUrls = [...category.urls]
                        .sort((left, right) => left.dropdown_element - right.dropdown_element)
                        .filter((item) => !item.logged_in_only || session.is_authenticated);

                      if (categoryUrls.length === 0) {
                        return null;
                      }
                      const dropdownId = `dropdown-${category.category_name
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, "")}`;

                      return (
                        <li key={category.category_name} className="nav-item dropdown">
                          <a
                            className="nav-link dropdown-toggle"
                            href="#"
                            id={dropdownId}
                            role="button"
                            data-bs-toggle="dropdown"
                            aria-expanded="false"
                          >
                            {category.category_name}
                          </a>
                          <ul
                            className="dropdown-menu dropdown-menu-dark"
                            aria-labelledby={dropdownId}
                          >
                            {categoryUrls.map((item) => {
                              if (session.is_authenticated && isLoginRoute(item.url)) {
                                return (
                                  <li key={`${category.category_name}-${item.dropdown_element}-logout`}>
                                    <LogoutButton className="dropdown-item site-header__logout-button" label="Logga ut" />
                                  </li>
                                );
                              }
                              return (
                                <li key={`${category.category_name}-${item.dropdown_element}-${item.url}`}>
                                  {renderNavLink(item.url, item.title, "dropdown-item")}
                                </li>
                              );
                            })}
                          </ul>
                        </li>
                      );
                    })
                  : showFallbackNav
                    ? [
                        showHome ? (
                          <li key="home" className="nav-item">
                            <Link href="/" className="nav-link">
                              Home
                            </Link>
                          </li>
                        ) : null,
                        <li key="members" className="nav-item">
                          <Link href="/members" className="nav-link">
                            Members
                          </Link>
                        </li>,
                        ...moduleNav.map((item) => (
                          <li key={item.moduleKey} className="nav-item">
                            <Link href={item.href} className="nav-link">
                              {item.label}
                            </Link>
                          </li>
                        )),
                      ]
                    : null}
              </ul>
            </div>
          </div>
        </div>
      </nav>
    </header>
  );
}
