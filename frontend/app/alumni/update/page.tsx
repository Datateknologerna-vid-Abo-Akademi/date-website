import { notFound } from "next/navigation";

import { AlumniUpdateRequestForm } from "@/components/alumni/update-request-form";
import { getSiteMeta } from "@/lib/api/queries";

export default async function AlumniUpdateRequestPage() {
  const siteMeta = await getSiteMeta();
  if (!siteMeta.enabled_modules.includes("alumni")) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Alumni</p>
        <h1>Request alumni update link</h1>
        <p>Enter your email to receive a one-time update token.</p>
      </section>
      <section className="panel">
        <AlumniUpdateRequestForm />
      </section>
    </div>
  );
}
