import type { NewsItem } from "@/lib/api/types";

const NEWS_TIME_ZONE = "Europe/Helsinki";

export function formatNewsDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("sv-FI", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: NEWS_TIME_ZONE,
  });
}

export function newsArticleHref(article: NewsItem, categoryOverride?: string) {
  const categorySlug = categoryOverride ?? article.category_slug;
  if (categorySlug) {
    return `/news/${encodeURIComponent(categorySlug)}/${encodeURIComponent(article.slug)}`;
  }
  return `/news/articles/${encodeURIComponent(article.slug)}`;
}

export function truncateNewsPreview(html: string, maxWords = 50) {
  const plain = html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (!plain) {
    return { preview: "", truncated: false };
  }
  const words = plain.split(" ");
  if (words.length <= maxWords) {
    return { preview: plain, truncated: false };
  }
  return { preview: `${words.slice(0, maxWords).join(" ")}...`, truncated: true };
}
