import { notFound } from "next/navigation";

import { AlumniUpdateForm } from "@/components/alumni/update-form";
import { getAlumniUpdateToken, getSiteMeta } from "@/lib/api/queries";

interface AlumniTokenPageProps {
  params: {
    token: string;
  };
}

export default async function AlumniTokenPage({ params }: AlumniTokenPageProps) {
  const siteMeta = await getSiteMeta();
  if (!siteMeta.enabled_modules.includes("alumni")) notFound();

  const tokenPayload = await getAlumniUpdateToken(params.token).catch(() => null);
  if (!tokenPayload) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Alumni</p>
        <h1>Update your alumni information</h1>
      </section>
      <section className="panel">
        <AlumniUpdateForm email={tokenPayload.email} token={params.token} />
      </section>
    </div>
  );
}
