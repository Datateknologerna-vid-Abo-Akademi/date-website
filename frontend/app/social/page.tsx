import Link from "next/link";

import { getSocialOverview } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function SocialPage() {
  await ensureModuleEnabled("social");
  const social = await getSocialOverview();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Social</p>
        <h1>Social Channels</h1>
        {social.harassment_contact_email ? (
          <p className="meta">Contact: {social.harassment_contact_email}</p>
        ) : null}
      </section>

      <section className="panel">
        <h2>Follow us</h2>
        <ul className="list list--spaced">
          {social.social_buttons.map(([icon, url]) => (
            <li key={`${icon}-${url}`}>
              <a href={url} target="_blank" rel="noreferrer">
                {url}
              </a>
              <p className="meta">{icon}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Safety reporting</h2>
        <p>Use the harassment report form for incidents and equality-plan concerns.</p>
        <Link href="/social/harassment">Open report form</Link>
      </section>
    </div>
  );
}
