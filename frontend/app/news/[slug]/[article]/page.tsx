import { notFound } from "next/navigation";

import { RichContent } from "@/components/rich-content";
import { getNewsArticle } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface NewsCategoryArticlePageProps {
  params: {
    slug: string;
    article: string;
  };
}

export default async function NewsCategoryArticlePage({ params }: NewsCategoryArticlePageProps) {
  await ensureModuleEnabled("news");
  const article = await getNewsArticle(params.article, params.slug).catch(() => null);
  if (!article) notFound();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">News</p>
        <h1>{article.title}</h1>
        <p className="meta">Category: {params.slug}</p>
      </section>
      <section className="panel">
        <RichContent html={article.content} />
      </section>
    </div>
  );
}
