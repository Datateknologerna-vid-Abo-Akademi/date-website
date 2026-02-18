import Link from "next/link";

import { getCtfEvents, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function CtfPage() {
  await ensureModuleEnabled("ctf");
  const session = await getSession();
  if (!session.is_authenticated) {
    return (
      <div className="page-shell">
        <section className="hero compact">
          <p className="eyebrow">CTF</p>
          <h1>Capture The Flag</h1>
          <p>You need to sign in to view CTF events.</p>
        </section>
        <section className="panel">
          <Link href="/members/login">Sign in</Link>
        </section>
      </div>
    );
  }

  const ctfEvents = await getCtfEvents().catch(() => null);
  if (!ctfEvents) {
    return (
      <div className="page-shell">
        <section className="hero compact">
          <p className="eyebrow">CTF</p>
          <h1>Not available</h1>
          <p>This association does not currently enable CTF.</p>
        </section>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">CTF</p>
        <h1>Capture The Flag</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
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
      </section>
    </div>
  );
}
