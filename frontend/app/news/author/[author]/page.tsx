import Link from "next/link";
import { RichContent } from "@/components/rich-content";
import { getNews } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";

import { formatNewsDate } from "../../news-utils";

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
    <div className="news-author-page container-md container-margin-top min-vh-100 p-1">
      <div className="container-size break-words">
        {posts.map((post) => (
          <div key={post.slug} className="content overflow-auto">
            <h1>{post.title}</h1>
            <h4 className="author">
              Skriven{" "}
              {post.published_time ? formatNewsDate(post.published_time) : "okänd tid"} av{" "}
              <Link href={`/news/author/${encodeURIComponent(author)}`}>{author}</Link>
            </h4>
            <RichContent html={post.content} />
          </div>
        ))}
        {posts.length === 0 ? <h1>Inga artiklar hittades...</h1> : null}
      </div>
    </div>
  );
}
