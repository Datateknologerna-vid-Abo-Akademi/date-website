import Link from "next/link";

import { PageHero, PageShell } from "@/components/ui/page-shell";

export default function NotFound() {
  return (
    <PageShell>
      <PageHero eyebrow="404" title="Page not found">
        <p>The requested resource does not exist in the decoupled frontend route set.</p>
        <p>
          <Link href="/">Return home</Link>
        </p>
      </PageHero>
    </PageShell>
  );
}
