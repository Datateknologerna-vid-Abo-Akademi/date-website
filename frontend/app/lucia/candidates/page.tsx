import Link from "next/link";
import { notFound } from "next/navigation";
import Image from "next/image";

import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getLuciaCandidates, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function LuciaCandidatesPage() {
  await ensureModuleEnabled("lucia");
  const session = await getSession();
  if (!session.is_authenticated) {
    return (
      <PageShell>
        <PageHero eyebrow="Lucia" title="Sign in required">
          <p>You need to sign in to view Lucia candidates.</p>
        </PageHero>
        <PagePanel>
          <Link href="/members/login">Sign in</Link>
        </PagePanel>
      </PageShell>
    );
  }

  const candidates = await getLuciaCandidates().catch(() => null);
  if (!candidates) notFound();

  return (
    <PageShell>
      <PageHero eyebrow="Lucia" title="Candidates" />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
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
      </PagePanel>
    </PageShell>
  );
}
