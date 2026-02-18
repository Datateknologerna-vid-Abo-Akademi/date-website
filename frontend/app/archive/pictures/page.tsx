import Link from "next/link";

import { getArchiveYears } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function ArchivePicturesPage() {
  await ensureModuleEnabled("archive");
  const payload = await getArchiveYears();
  const sortedYears = Object.entries(payload.year_albums).sort((a, b) => Number(b[0]) - Number(a[0]));

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Archive</p>
        <h1>Picture Years</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {sortedYears.map(([year, albumCount]) => (
            <li key={year}>
              <Link href={`/archive/pictures/${year}`}>
                {year} ({albumCount} albums)
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
