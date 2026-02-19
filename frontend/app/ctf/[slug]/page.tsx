import Link from "next/link";
import { notFound } from "next/navigation";

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
      <div className="page-shell">
        <section className="hero compact">
          <p className="eyebrow">CTF</p>
          <h1>Sign in required</h1>
          <p>You need to sign in to view this CTF event.</p>
        </section>
        <section className="panel">
          <Link href="/members/login">Sign in</Link>
        </section>
      </div>
    );
  }

  const payload = await getCtfEvent(slug).catch(() => null);
  if (!payload) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">CTF</p>
        <h1>{payload.ctf.title}</h1>
        <p className="meta">
          {new Date(payload.ctf.start_date).toLocaleString()} - {new Date(payload.ctf.end_date).toLocaleString()}
        </p>
      </section>
      <section className="panel">
        <p>{payload.user_has_solved_any_flag ? "You have solved at least one flag." : "No solved flags yet."}</p>
        <ul className="list">
          {payload.flags.map((flag) => (
            <li key={flag.slug} className="row-line">
              <Link href={`/ctf/${slug}/${flag.slug}`}>{flag.title}</Link>
              <span className="meta">{flag.is_solved ? `Solved by ${flag.solver_name}` : "Open"}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
