import type { Metadata } from "next";
import type { CSSProperties } from "react";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { getSiteMeta } from "@/lib/api/queries";

import "./globals.css";

export const metadata: Metadata = {
  title: "Association Portal",
  description: "Decoupled frontend for association sites",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const siteMeta = await getSiteMeta();
  const theme = siteMeta.association_theme;

  return (
    <html lang={siteMeta.language_code}>
      <body
        style={
          {
            "--theme-background": theme.palette.background,
            "--theme-surface": theme.palette.surface,
            "--theme-text": theme.palette.text,
            "--theme-text-muted": theme.palette.text_muted,
            "--theme-primary": theme.palette.primary,
            "--theme-secondary": theme.palette.secondary,
            "--theme-accent": theme.palette.accent,
            "--theme-border": theme.palette.border,
            "--theme-font-heading": theme.font_heading,
            "--theme-font-body": theme.font_body,
          } as CSSProperties
        }
      >
        <SiteHeader siteMeta={siteMeta} />
        <main className="site-main">{children}</main>
        <SiteFooter siteMeta={siteMeta} />
      </body>
    </html>
  );
}
