import Link from "next/link";

import { getArchiveYears } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

export default async function ArchivePicturesPage() {
  await ensureModuleEnabled("archive");
  const payload = await getArchiveYears();
  const sortedYears = Object.entries(payload.year_albums).sort((a, b) => Number(b[0]) - Number(a[0]));

  return (
    <PageShell>
      <PageHero eyebrow="Archive" title="Picture Years" />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {sortedYears.map(([year, albumCount]) => (
            <li key={year}>
              <Link href={`/archive/pictures/${year}`}>
                {year} ({albumCount} albums)
              </Link>
            </li>
          ))}
        </ul>
      </PagePanel>
    </PageShell>
  );
}
