import { AlumniUpdateRequestForm } from "@/components/alumni/update-request-form";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function AlumniUpdateRequestPage() {
  await ensureModuleEnabled("alumni");

  return (
    <PageShell>
      <PageHero eyebrow="Alumni" title="Request alumni update link">
        <p>Enter your email to receive a one-time update token.</p>
      </PageHero>
      <PagePanel>
        <AlumniUpdateRequestForm />
      </PagePanel>
    </PageShell>
  );
}
