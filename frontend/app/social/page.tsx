import { ensureModuleEnabled } from "@/lib/module-guards";
import { PageHero, PageShell } from "@/components/ui/page-shell";

export default async function SocialPage() {
  await ensureModuleEnabled("social");

  return (
    <PageShell>
      <PageHero eyebrow="Social" title="Social" />
    </PageShell>
  );
}
