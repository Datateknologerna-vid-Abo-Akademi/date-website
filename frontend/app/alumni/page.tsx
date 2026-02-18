import Link from "next/link";
import { notFound } from "next/navigation";

import { getSiteMeta } from "@/lib/api/queries";

export default async function AlumniPage() {
  const siteMeta = await getSiteMeta();
  if (!siteMeta.enabled_modules.includes("alumni")) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Alumni</p>
        <h1>Alumni Portal</h1>
      </section>
      <section className="panel">
        <div className="link-grid">
          <Link href="/alumni/signup">Register</Link>
          <Link href="/alumni/update">Request update token</Link>
        </div>
      </section>
    </div>
  );
}
