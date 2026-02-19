import { notFound } from "next/navigation";

import { PollVoteForm } from "@/components/polls/poll-vote-form";
import { getPoll } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface PollDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default async function PollDetailPage({ params }: PollDetailPageProps) {
  await ensureModuleEnabled("polls");
  const { id } = await params;
  const pollId = Number(id);
  if (Number.isNaN(pollId)) notFound();

  const poll = await getPoll(pollId).catch(() => null);
  if (!poll) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Poll</p>
        <h1>{poll.question_text}</h1>
      </section>
      <section className="panel">
        <PollVoteForm initialPoll={poll} />
      </section>
    </div>
  );
}
