import type { SiteMeta } from "@/lib/api/types";

interface SiteFooterProps {
  siteMeta: SiteMeta;
}

export function SiteFooter({ siteMeta }: SiteFooterProps) {
  const variables = siteMeta.content_variables;
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p>{(variables.ASSOCIATION_NAME_FULL as string | undefined) ?? "Association"}</p>
        <p>{(variables.ASSOCIATION_EMAIL as string | undefined) ?? ""}</p>
      </div>
    </footer>
  );
}
