import { notFound } from "next/navigation";
import Link from "next/link";

import { RichContent } from "@/components/rich-content";
import { getNews, getNewsArticle } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

import { formatNewsDate, newsArticleHref, truncateNewsPreview } from "../news-utils";

interface NewsDetailPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export default async function NewsDetailPage({ params }: NewsDetailPageProps) {
  await ensureModuleEnabled("news");
  const { slug } = await params;
  const article = await getNewsArticle(slug).catch(() => null);

  if (!article) {
    const categoryPosts = await getNews(slug).catch(() => null);
    if (!categoryPosts) notFound();
    return (
      <div className="news-index-page container-md container-margin-top min-vh-100 p-1">
        <div className="container-size break-words">
          {categoryPosts.map((post) => {
            const preview = truncateNewsPreview(post.content, 50);
            const articleHref = newsArticleHref(post, slug);
            return (
              <div key={post.slug} className="content overflow-auto">
                <Link href={articleHref}>
                  <h2>{post.title}</h2>
                </Link>
                <h4 className="help-text">
                  {post.author_name}
                  {post.published_time ? `, ${formatNewsDate(post.published_time)}` : ""}
                </h4>
                <div>{preview.preview}</div>
                {preview.truncated ? (
                  <Link href={articleHref}>
                    <p className="more-button">Läs mera...</p>
                  </Link>
                ) : null}
              </div>
            );
          })}
          {categoryPosts.length === 0 ? (
            <h4 className="text-center">Inga nyheter hittades...</h4>
          ) : null}
        </div>
      </div>
    );
  }

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
