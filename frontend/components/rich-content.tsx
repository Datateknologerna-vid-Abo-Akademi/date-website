import { normalizeCkeditorHtml } from "@/lib/content/ckeditor";

interface RichContentProps {
  html: string;
}

export function RichContent({ html }: RichContentProps) {
  const normalizedHtml = normalizeCkeditorHtml(html);
  return <article className="rich-content" dangerouslySetInnerHTML={{ __html: normalizedHtml }} />;
}
