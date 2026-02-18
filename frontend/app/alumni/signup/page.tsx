import Link from "next/link";
import { notFound } from "next/navigation";

import { AlumniSignupForm } from "@/components/alumni/signup-form";
import { getSiteMeta } from "@/lib/api/queries";

export default async function AlumniSignupPage() {
  const siteMeta = await getSiteMeta();
  if (!siteMeta.enabled_modules.includes("alumni")) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Alumni</p>
        <h1>Alumni Registration</h1>
        <p>Register as alumni or request profile update.</p>
      </section>
      <section className="panel">
        <AlumniSignupForm />
      </section>
      <section className="panel">
        <p>Already in the alumni register?</p>
        <Link href="/alumni/update">Request update token</Link>
      </section>
    </div>
  );
}
