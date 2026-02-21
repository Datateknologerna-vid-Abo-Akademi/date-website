import type { Metadata } from "next";
import { Chakra_Petch, Josefin_Sans } from "next/font/google";
import Script from "next/script";

import { CookieBanner } from "@/components/cookie-banner";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { getSession, getSiteMeta } from "@/lib/api/queries";
import { normalizeAssociationBrand } from "@/lib/theme/runtime-theme";

import Providers from "./providers";
import "./globals.css";

const chakraPetch = Chakra_Petch({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
  variable: "--font-chakra",
});

const josefinSans = Josefin_Sans({
  weight: ["300", "400", "600"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-josefin",
});

export async function generateMetadata(): Promise<Metadata> {
  const siteMeta = await getSiteMeta().catch(() => null);
  const associationName =
    (((siteMeta?.content_variables as Record<string, unknown>)?.ASSOCIATION_NAME) as string | undefined) ?? "Association Portal";

  return {
    title: {
      template: `%s - ${associationName}`,
      default: associationName,
    },
    description: `Decoupled frontend for ${associationName}`,
    icons: [
      {
        rel: "shortcut icon",
        type: "image/png",
        url: "/static/core/images/logo.ico",
      },
    ],
  };
}

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

  return (
    <html lang={siteMeta.language_code}>
      <head>
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
        className={`association-${brand || "default"} ${josefinSans.variable} ${chakraPetch.variable}`}
        data-association={brand || "default"}
      >
        <Providers>
          <SiteHeader siteMeta={siteMeta} session={session} />
          <main className="site-main">{children}</main>
          <SiteFooter siteMeta={siteMeta} />
          <CookieBanner />
        </Providers>
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
