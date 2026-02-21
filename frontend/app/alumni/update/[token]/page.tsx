import { notFound } from "next/navigation";

import { AlumniUpdateForm } from "@/components/alumni/update-form";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { getAlumniUpdateToken } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface AlumniTokenPageProps {
  params: Promise<{
    token: string;
  }>;
}

export default async function AlumniTokenPage({ params }: AlumniTokenPageProps) {
  await ensureModuleEnabled("alumni");
  const { token } = await params;

  const tokenPayload = await getAlumniUpdateToken(token).catch(() => null);
  if (!tokenPayload) notFound();

  return (
    <PageShell>
      <PageHero eyebrow="Alumni" title="Update your alumni information" />
      <PagePanel>
        <AlumniUpdateForm email={tokenPayload.email} token={token} />
      </PagePanel>
    </PageShell>
  );
}
