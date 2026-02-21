import { getAds } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

export default async function AdsPage() {
  await ensureModuleEnabled("ads");
  const ads = await getAds();

  return (
    <PageShell>
      <PageHero eyebrow="Ads" title="Sponsors and Partners" />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {ads.map((ad) => (
            <li key={ad.ad_url}>
              <a href={ad.company_url || ad.ad_url} target="_blank" rel="noreferrer">
                {ad.company_url || ad.ad_url}
              </a>
              <p className="meta">{ad.ad_url}</p>
            </li>
          ))}
        </ul>
      </PagePanel>
    </PageShell>
  );
}
