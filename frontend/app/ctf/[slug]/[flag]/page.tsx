import { notFound } from "next/navigation";

import { FlagGuessForm } from "@/components/ctf/flag-guess-form";
import { RichContent } from "@/components/rich-content";
import { getCtfFlag, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface CtfFlagPageProps {
  params: {
    slug: string;
    flag: string;
  };
}

export default async function CtfFlagPage({ params }: CtfFlagPageProps) {
  await ensureModuleEnabled("ctf");
  const session = await getSession();
  if (!session.is_authenticated) {
    return notFound();
  }

  const payload = await getCtfFlag(params.slug, params.flag).catch(() => null);
  if (!payload) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">CTF Flag</p>
        <h1>{payload.flag.title}</h1>
        <p className="meta">
          {payload.flag.is_solved
            ? `Solved by ${payload.flag.solver_name}`
            : "Unsolved"}
        </p>
      </section>
      <section className="panel">
        <RichContent html={payload.flag.clues} />
      </section>
      <section className="panel">
        <FlagGuessForm ctfSlug={params.slug} flagSlug={params.flag} canSubmit={payload.can_submit} />
      </section>
    </div>
  );
}
