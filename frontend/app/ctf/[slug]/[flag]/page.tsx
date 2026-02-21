import { notFound } from "next/navigation";

import { FlagGuessForm } from "@/components/ctf/flag-guess-form";
import { RichContent } from "@/components/rich-content";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getCtfFlag, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface CtfFlagPageProps {
  params: Promise<{
    slug: string;
    flag: string;
  }>;
}

export default async function CtfFlagPage({ params }: CtfFlagPageProps) {
  await ensureModuleEnabled("ctf");
  const session = await getSession();
  if (!session.is_authenticated) {
    return notFound();
  }
  const { slug, flag } = await params;

  const payload = await getCtfFlag(slug, flag).catch(() => null);
  if (!payload) notFound();

  return (
    <PageShell>
      <PageHero
        eyebrow="CTF Flag"
        title={payload.flag.title}
        meta={payload.flag.is_solved ? `Solved by ${payload.flag.solver_name}` : "Unsolved"}
      />
      <PagePanel>
        <RichContent html={payload.flag.clues} />
      </PagePanel>
      <PagePanel>
        <FlagGuessForm ctfSlug={slug} flagSlug={flag} canSubmit={payload.can_submit} />
      </PagePanel>
    </PageShell>
  );
}
