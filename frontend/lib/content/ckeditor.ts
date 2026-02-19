const FIGURE_MEDIA_OEMBED_REGEX =
  /<figure\b[^>]*class=(["'])[^"']*\bmedia\b[^"']*\1[^>]*>[\s\S]*?<oembed\b[^>]*url=(["'])(.*?)\2[^>]*>\s*<\/oembed>[\s\S]*?<\/figure>/gi;
const OEMBED_REGEX = /<oembed\b[^>]*url=(["'])(.*?)\1[^>]*>\s*<\/oembed>/gi;

function escapeHtmlAttribute(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function extractStartSeconds(raw: string | null): number | null {
  if (!raw) return null;
  if (/^\d+$/.test(raw)) return Number(raw);
  const match = raw.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/i);
  if (!match) return null;

  const hours = Number(match[1] ?? 0);
  const minutes = Number(match[2] ?? 0);
  const seconds = Number(match[3] ?? 0);
  const total = hours * 3600 + minutes * 60 + seconds;
  return total > 0 ? total : null;
}

function normalizeHost(host: string): string {
  return host.toLowerCase().replace(/^www\./, "");
}

function youtubeEmbedUrl(url: URL): string | null {
  const host = normalizeHost(url.hostname);
  let videoId: string | null = null;

  if (host === "youtu.be") {
    videoId = url.pathname.split("/").filter(Boolean)[0] ?? null;
  } else if (
    host === "youtube.com" ||
    host === "m.youtube.com" ||
    host === "youtube-nocookie.com"
  ) {
    if (url.pathname === "/watch") {
      videoId = url.searchParams.get("v");
    } else if (url.pathname.startsWith("/embed/")) {
      videoId = url.pathname.split("/").filter(Boolean)[1] ?? null;
    } else if (url.pathname.startsWith("/shorts/")) {
      videoId = url.pathname.split("/").filter(Boolean)[1] ?? null;
    }
  }

  if (!videoId) return null;
  const safeVideoId = videoId.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!safeVideoId) return null;

  const embedUrl = new URL(`https://www.youtube.com/embed/${safeVideoId}`);
  const startSeconds =
    extractStartSeconds(url.searchParams.get("start")) ??
    extractStartSeconds(url.searchParams.get("t"));
  if (startSeconds !== null) {
    embedUrl.searchParams.set("start", String(startSeconds));
  }
  return embedUrl.toString();
}

function vimeoEmbedUrl(url: URL): string | null {
  const host = normalizeHost(url.hostname);
  if (host !== "vimeo.com" && host !== "player.vimeo.com") return null;

  const firstSegment = url.pathname.split("/").filter(Boolean).pop() ?? "";
  if (!/^\d+$/.test(firstSegment)) return null;
  return `https://player.vimeo.com/video/${firstSegment}`;
}

function toEmbedUrl(rawUrl: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return null;
  }

  const youtube = youtubeEmbedUrl(parsed);
  if (youtube) return youtube;

  const vimeo = vimeoEmbedUrl(parsed);
  if (vimeo) return vimeo;

  return null;
}

function mediaHtmlFromUrl(rawUrl: string): string {
  const embedUrl = toEmbedUrl(rawUrl);
  if (!embedUrl) {
    const fallbackHref = escapeHtmlAttribute(rawUrl);
    return `<a href="${fallbackHref}" target="_blank" rel="noopener noreferrer">${fallbackHref}</a>`;
  }

  const safeSrc = escapeHtmlAttribute(embedUrl);
  return `<div class="ck-media__wrapper"><iframe src="${safeSrc}" loading="lazy" allowfullscreen allow="autoplay; encrypted-media; picture-in-picture"></iframe></div>`;
}

function mediaFigureFromUrl(rawUrl: string): string {
  return `<figure class="media">${mediaHtmlFromUrl(rawUrl)}</figure>`;
}

export function normalizeCkeditorHtml(html: string): string {
  const withMediaFigures = html.replace(
    FIGURE_MEDIA_OEMBED_REGEX,
    (_match, _classQuote, _urlQuote, rawUrl: string) => mediaFigureFromUrl(rawUrl),
  );

  return withMediaFigures.replace(
    OEMBED_REGEX,
    (_match, _urlQuote, rawUrl: string) => mediaHtmlFromUrl(rawUrl),
  );
}

