import Link from "next/link";
import { notFound } from "next/navigation";
import Image from "next/image";

import { getLuciaCandidates, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function LuciaCandidatesPage() {
  await ensureModuleEnabled("lucia");
  const session = await getSession();
  if (!session.is_authenticated) {
    return (
      <div className="page-shell">
        <section className="hero compact">
          <p className="eyebrow">Lucia</p>
          <h1>Sign in required</h1>
          <p>You need to sign in to view Lucia candidates.</p>
        </section>
        <section className="panel">
          <Link href="/members/login">Sign in</Link>
        </section>
      </div>
    );
  }

  const candidates = await getLuciaCandidates().catch(() => null);
  if (!candidates) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Lucia</p>
        <h1>Candidates</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {candidates.map((candidate) => (
            <li key={candidate.slug}>
              <h2>
                <Link href={`/lucia/candidates/${candidate.slug}`}>{candidate.title}</Link>
              </h2>
              {candidate.img_url ? (
                <Image
                  src={candidate.img_url}
                  alt={candidate.title}
                  width={420}
                  height={300}
                  className="candidate-image"
                  unoptimized
                />
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
