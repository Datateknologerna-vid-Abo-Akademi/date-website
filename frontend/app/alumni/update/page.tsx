import { AlumniUpdateRequestForm } from "@/components/alumni/update-request-form";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function AlumniUpdateRequestPage() {
  await ensureModuleEnabled("alumni");

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
