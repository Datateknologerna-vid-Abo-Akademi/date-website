interface RichContentProps {
  html: string;
}

export function RichContent({ html }: RichContentProps) {
  return <article className="rich-content" dangerouslySetInnerHTML={{ __html: html }} />;
}
