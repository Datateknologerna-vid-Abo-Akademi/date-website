import { redirect } from "next/navigation";

import { HomePageView } from "@/features/home/home-page-view";
import { getAboutText, getHeroSubtitle } from "@/features/home/utils";
import { getHomeData, getSiteMeta } from "@/lib/api/queries";
import {
  BIOCUM_HERO_LOGO_SVG,
  DATE_HERO_LOGO_SVG,
  KK_HERO_LOGO_SVG,
} from "@/lib/legacy-hero-logos";
import { isModuleEnabled } from "@/lib/modules";
import { resolveTenantHomeConfig } from "@/lib/tenants";

const INLINE_HERO_LOGOS: Record<string, string> = {
  date: DATE_HERO_LOGO_SVG,
  demo: DATE_HERO_LOGO_SVG,
  kk: KK_HERO_LOGO_SVG,
  biocum: BIOCUM_HERO_LOGO_SVG,
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

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
  const associationFullName =
    (siteMeta.content_variables.ASSOCIATION_NAME_FULL as string | undefined) ?? "";
  const brand = (siteMeta.association_theme.brand ?? "").toLowerCase();
  const homeConfig = resolveTenantHomeConfig(brand);
  const aboutText = getAboutText(brand);
  const heroSubtitle = getHeroSubtitle(brand, associationName, associationFullName);
  const heroLogo = siteMeta.branding?.logo_header_url || "/static/core/images/headerlogo.png";
  const inlineHeroLogo = INLINE_HERO_LOGOS[brand] || "";

  return (
    <HomePageView
      homeData={homeData}
      brand={brand}
      associationName={associationName}
      heroSubtitle={heroSubtitle}
      heroLogo={heroLogo}
      inlineHeroLogo={inlineHeroLogo}
      aboutText={aboutText}
      showNews={showNews && homeConfig.showNews}
      showEvents={showEvents && homeConfig.showEvents}
    />
  );
}
