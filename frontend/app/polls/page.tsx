import Link from "next/link";

import { getPolls } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function PollsPage() {
  await ensureModuleEnabled("polls");
  const polls = await getPolls();
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Polls</p>
        <h1>Active Polls</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {polls.map((poll) => (
            <li key={poll.id}>
              <h2>
                <Link href={`/polls/${poll.id}`}>{poll.question_text}</Link>
              </h2>
              <p className="meta">Published {new Date(poll.pub_date).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
