import Link from "next/link";

import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import listStyles from "@/components/ui/list-primitives.module.css";
import { getCtfEvents, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function CtfPage() {
  await ensureModuleEnabled("ctf");
  const session = await getSession();
  if (!session.is_authenticated) {
    return (
      <PageShell>
        <PageHero eyebrow="CTF" title="Capture The Flag">
          <p>You need to sign in to view CTF events.</p>
        </PageHero>
        <PagePanel>
          <Link href="/members/login">Sign in</Link>
        </PagePanel>
      </PageShell>
    );
  }

  const ctfEvents = await getCtfEvents().catch(() => null);
  if (!ctfEvents) {
    return (
      <PageShell>
        <PageHero eyebrow="CTF" title="Not available">
          <p>This association does not currently enable CTF.</p>
        </PageHero>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHero eyebrow="CTF" title="Capture The Flag" />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {ctfEvents.map((ctf) => (
            <li key={ctf.slug}>
              <h2>
                <Link href={`/ctf/${ctf.slug}`}>{ctf.title}</Link>
              </h2>
              <p className="meta">
                {new Date(ctf.start_date).toLocaleString()} - {new Date(ctf.end_date).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      </PagePanel>
    </PageShell>
  );
}
