import type { Metadata } from "next";
import Script from "next/script";
import type { CSSProperties } from "react";

import { CookieBanner } from "@/components/cookie-banner";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { getSession, getSiteMeta } from "@/lib/api/queries";
import {
  buildThemeStyleVars,
  normalizeAssociationBrand,
  resolveUiProfile,
} from "@/lib/theme/runtime-theme";

import "./globals.css";

export const metadata: Metadata = {
  title: "Association Portal",
  description: "Decoupled frontend for association sites",
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [siteMeta, session] = await Promise.all([
    getSiteMeta(),
    getSession().catch(() => ({ is_authenticated: false })),
  ]);
  const theme = siteMeta.association_theme;
  const brand = normalizeAssociationBrand(theme.brand ?? "");
  const styleVars = buildThemeStyleVars(theme, brand);
  const uiProfile = resolveUiProfile(brand);

  return (
    <html lang={siteMeta.language_code}>
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css?family=Chakra+Petch"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css?family=Josefin+Sans:300,400,400i,600"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css"
          integrity="sha384-1BmE4kWBq78iYhFldvKuhfTAU6auU8tT94WrHftjDbrCEXSU1oBoqyl2QvZ6jIW3"
          crossOrigin="anonymous"
        />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
        />
        <link
          rel="stylesheet"
          href="https://maxst.icons8.com/vue-static/landings/line-awesome/font-awesome-line-awesome/css/all.min.css"
        />
      </head>
      <body
        className={`association-${brand || "default"}`}
        data-association={brand || "default"}
        data-ui-profile={uiProfile}
        style={styleVars as CSSProperties}
      >
        <SiteHeader siteMeta={siteMeta} session={session} />
        <main className="site-main">{children}</main>
        <SiteFooter siteMeta={siteMeta} />
        <CookieBanner />
        <Script
          src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"
          integrity="sha384-ka7Sk0Gln4gmtz2MlQnikT1wXgYsOg+OMhuP+IlRH9sENBO0LRn5q+8nbTov4+1p"
          crossOrigin="anonymous"
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
