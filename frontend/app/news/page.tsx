import Link from "next/link";

import { getNews } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

import { formatNewsDate, newsArticleHref, truncateNewsPreview } from "./news-utils";

export default async function NewsPage() {
  await ensureModuleEnabled("news");
  const news = await getNews();

  return (
    <div className="news-index-page container-md container-margin-top min-vh-100 p-1">
      <div className="container-size break-words">
        {news.map((article) => {
          const preview = truncateNewsPreview(article.content, 50);
          const articleHref = newsArticleHref(article);
          return (
            <div key={article.slug} className="content overflow-auto">
              <Link href={articleHref}>
                <h2>{article.title}</h2>
              </Link>
              <h4 className="help-text">
                {article.author_name}
                {article.published_time ? `, ${formatNewsDate(article.published_time)}` : ""}
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
        {news.length === 0 ? <h4 className="text-center">Inga nyheter hittades...</h4> : null}
      </div>
    </div>
  );
}
