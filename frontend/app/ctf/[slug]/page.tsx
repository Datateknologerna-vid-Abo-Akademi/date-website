import Link from "next/link";
import { notFound } from "next/navigation";

import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getCtfEvent, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface CtfDetailPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function CtfDetailPage({ params }: CtfDetailPageProps) {
  await ensureModuleEnabled("ctf");
  const session = await getSession();
  const { slug } = await params;
  if (!session.is_authenticated) {
    return (
      <PageShell>
        <PageHero eyebrow="CTF" title="Sign in required">
          <p>You need to sign in to view this CTF event.</p>
        </PageHero>
        <PagePanel>
          <Link href="/members/login">Sign in</Link>
        </PagePanel>
      </PageShell>
    );
  }

  const payload = await getCtfEvent(slug).catch(() => null);
  if (!payload) notFound();

  return (
    <PageShell>
      <PageHero
        eyebrow="CTF"
        title={payload.ctf.title}
        meta={`${new Date(payload.ctf.start_date).toLocaleString()} - ${new Date(payload.ctf.end_date).toLocaleString()}`}
      />
      <PagePanel>
        <p>{payload.user_has_solved_any_flag ? "You have solved at least one flag." : "No solved flags yet."}</p>
        <ul className={listStyles.list}>
          {payload.flags.map((flag) => (
            <li key={flag.slug} className={listStyles.rowLine}>
              <Link href={`/ctf/${slug}/${flag.slug}`}>{flag.title}</Link>
              <span className="meta">{flag.is_solved ? `Solved by ${flag.solver_name}` : "Open"}</span>
            </li>
          ))}
        </ul>
      </PagePanel>
    </PageShell>
  );
}
