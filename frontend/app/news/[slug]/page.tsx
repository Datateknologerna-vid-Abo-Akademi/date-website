import { notFound } from "next/navigation";
import Link from "next/link";

import { RichContent } from "@/components/rich-content";
import { getNews, getNewsArticle } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

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
      <div className="page-shell">
        <section className="hero compact">
          <p className="eyebrow">News</p>
          <h1>Category: {slug}</h1>
        </section>
        <section className="panel">
          <ul className="list list--spaced">
            {categoryPosts.map((post) => (
              <li key={post.slug}>
                <h2>
                  <Link href={`/news/${slug}/${post.slug}`}>{post.title}</Link>
                </h2>
                <p className="meta">{post.author_name}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    );
  }
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">News</p>
        <h1>{article.title}</h1>
        <p className="meta">
          {article.author_name}
          {article.published_time ? ` - ${new Date(article.published_time).toLocaleDateString()}` : ""}
        </p>
      </section>
      <section className="panel">
        <RichContent html={article.content} />
      </section>
    </div>
  );
}
