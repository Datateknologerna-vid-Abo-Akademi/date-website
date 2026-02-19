import Link from "next/link";

import { getNews } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

interface NewsAuthorPageProps {
  params: Promise<{
    author: string;
  }>;
}

export default async function NewsAuthorPage({ params }: NewsAuthorPageProps) {
  await ensureModuleEnabled("news");
  const { author: encodedAuthor } = await params;
  const author = decodeURIComponent(encodedAuthor);
  const posts = await getNews(undefined, author);

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">News</p>
        <h1>Author: {author}</h1>
      </section>
      <section className="panel">
        <ul className="list list--spaced">
          {posts.map((post) => (
            <li key={post.slug}>
              <h2>
                <Link href={`/news/articles/${post.slug}`}>{post.title}</Link>
              </h2>
              <p className="meta">
                {post.published_time ? new Date(post.published_time).toLocaleDateString() : "No date"}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
