import { getAds } from "@/lib/api/queries";

export default async function AdsPage() {
  const ads = await getAds();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Ads</p>
        <h1>Sponsors and Partners</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {ads.map((ad) => (
            <li key={ad.ad_url}>
              <a href={ad.company_url || ad.ad_url} target="_blank" rel="noreferrer">
                {ad.company_url || ad.ad_url}
              </a>
              <p className="meta">{ad.ad_url}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
