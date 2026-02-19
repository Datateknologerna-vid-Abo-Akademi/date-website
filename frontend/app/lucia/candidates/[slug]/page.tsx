import { notFound } from "next/navigation";
import Image from "next/image";

import { RichContent } from "@/components/rich-content";
import { getLuciaCandidate, getSession } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface LuciaCandidatePageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function LuciaCandidatePage({ params }: LuciaCandidatePageProps) {
  await ensureModuleEnabled("lucia");
  const session = await getSession();
  if (!session.is_authenticated) notFound();
  const { slug } = await params;

  const candidate = await getLuciaCandidate(slug).catch(() => null);
  if (!candidate) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Lucia Candidate</p>
        <h1>{candidate.title}</h1>
      </section>
      <section className="panel">
        {candidate.img_url ? (
          <Image
            src={candidate.img_url}
            alt={candidate.title}
            width={420}
            height={300}
            className="candidate-image"
            unoptimized
          />
        ) : null}
        <RichContent html={candidate.content} />
        <a href={candidate.poll_url} target="_blank" rel="noreferrer">
          Vote for candidate
        </a>
      </section>
    </div>
  );
}
