import Link from "next/link";

import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function AlumniPage() {
  await ensureModuleEnabled("alumni");

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
