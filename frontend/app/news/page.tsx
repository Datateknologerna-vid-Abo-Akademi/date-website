import Link from "next/link";

import { getNews } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

export default async function NewsPage() {
  await ensureModuleEnabled("news");
  const news = await getNews();
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">News</p>
        <h1>Latest Articles</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {news.map((article) => (
            <li key={article.slug}>
              <h2>
                <Link href={`/news/articles/${article.slug}`}>{article.title}</Link>
              </h2>
              <p className="meta">
                {article.author_name}
                {article.published_time
                  ? ` - ${new Date(article.published_time).toLocaleDateString()}`
                  : ""}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
