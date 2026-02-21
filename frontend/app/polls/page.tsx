import Link from "next/link";

import { getPolls } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";
import listStyles from "@/components/ui/list-primitives.module.css";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";

export default async function PollsPage() {
  await ensureModuleEnabled("polls");
  const polls = await getPolls();
  return (
    <PageShell>
      <PageHero eyebrow="Polls" title="Active Polls" />
      <PagePanel>
        <ul className={listStyles.listSpaced}>
          {polls.map((poll) => (
            <li key={poll.id}>
              <h2>
                <Link href={`/polls/${poll.id}`}>{poll.question_text}</Link>
              </h2>
              <p className="meta">Published {new Date(poll.pub_date).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      </PagePanel>
    </PageShell>
  );
}
