import { notFound } from "next/navigation";
import Link from "next/link";

import { RichContent } from "@/components/rich-content";
import { getNewsArticle } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

import { formatNewsDate } from "../../news-utils";

interface LegacyNewsArticlePageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function LegacyNewsArticlePage({ params }: LegacyNewsArticlePageProps) {
  await ensureModuleEnabled("news");
  const { slug } = await params;
  const article = await getNewsArticle(slug).catch(() => null);
  if (!article) notFound();

  return (
    <div className="news-article-page container-md container-margin-top min-vh-100 p-1">
      <div className="container-size break-words">
        <div className="content overflow-auto">
          <h2>{article.title}</h2>
          <h4 className="author">
            Skriven{" "}
            {article.published_time ? formatNewsDate(article.published_time) : "okänd tid"} av{" "}
            <Link href={`/news/author/${encodeURIComponent(article.author_name)}`}>
              {article.author_name}
            </Link>
          </h4>
          <RichContent html={article.content} />
        </div>
      </div>
    </div>
  );
}
