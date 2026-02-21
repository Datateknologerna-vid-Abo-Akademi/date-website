import { notFound } from "next/navigation";

import { PollVoteForm } from "@/components/polls/poll-vote-form";
import { PageHero, PagePanel, PageShell } from "@/components/ui/page-shell";
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
    <PageShell>
      <PageHero eyebrow="Poll" title={poll.question_text} />
      <PagePanel>
        <PollVoteForm initialPoll={poll} />
      </PagePanel>
    </PageShell>
  );
}
