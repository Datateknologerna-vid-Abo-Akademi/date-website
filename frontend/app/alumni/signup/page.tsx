import Link from "next/link";

import { AlumniSignupForm } from "@/components/alumni/signup-form";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function AlumniSignupPage() {
  await ensureModuleEnabled("alumni");

  return (
    <PageShell>
      <PageHero eyebrow="Alumni" title="Alumni Registration">
        <p>Register as alumni or request profile update.</p>
      </PageHero>
      <PagePanel>
        <AlumniSignupForm />
      </PagePanel>
      <PagePanel>
        <p>Already in the alumni register?</p>
        <Link href="/alumni/update">Request update token</Link>
      </PagePanel>
    </PageShell>
  );
}
