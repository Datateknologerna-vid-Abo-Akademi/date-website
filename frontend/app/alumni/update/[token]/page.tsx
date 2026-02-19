import { notFound } from "next/navigation";

import { AlumniUpdateForm } from "@/components/alumni/update-form";
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
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Alumni</p>
        <h1>Update your alumni information</h1>
      </section>
      <section className="panel">
        <AlumniUpdateForm email={tokenPayload.email} token={token} />
      </section>
    </div>
  );
}
