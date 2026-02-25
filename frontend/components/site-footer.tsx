/* eslint-disable @next/next/no-img-element */
import type { SiteMeta } from "@/lib/api/types";
import styles from "@/components/site-footer.module.css";

interface SiteFooterProps {
  siteMeta: SiteMeta;
}

function getSocialButtons(value: unknown): Array<[string, string]> {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry): entry is [string, string] => {
      return (
        Array.isArray(entry) &&
        entry.length >= 2 &&
        typeof entry[0] === "string" &&
        typeof entry[1] === "string"
      );
    })
    .map((entry) => [entry[0], entry[1]]);
}

function normalizeIconClass(iconClass: string) {
  if (iconClass.includes("fa-")) return iconClass;
  return `fa-${iconClass}`;
}

export function SiteFooter({ siteMeta }: SiteFooterProps) {
  const variables = siteMeta.content_variables;
  const socialButtons = getSocialButtons(variables.SOCIAL_BUTTONS);
  const associationNameFull =
    (variables.ASSOCIATION_NAME_FULL as string | undefined) ?? "Association";
  const associationShortName =
    (variables.ASSOCIATION_NAME_SHORT as string | undefined) ?? "Association";
  const footerLogoSrc = siteMeta.branding?.logo_footer_url || "/static/core/images/footerlogo.png";

  return (
    <footer className={`container site-footer legacy-site-footer ${styles.root}`}>
      <hr />
      <section className={`col text-center ${styles.socialSection}`}>
        {socialButtons.map(([iconClass, href]) => (
          <a
            key={`${iconClass}-${href}`}
            className="btn btn-outline-light btn-floating m-1"
            href={href}
            target="_blank"
            rel="noreferrer"
            role="button"
            aria-label={iconClass}
          >
            <i className={`fab ${normalizeIconClass(iconClass).replace("fab ", "")}`} />
          </a>
        ))}
      </section>
      <div className={`row align-middle align-items-center justify-content-center ${styles.row}`}>
        <div className="col-4 text-center">
            <img
              className={`footer-img img-fluid ${styles.footerImage}`}
              alt={`${associationShortName} footer logo`}
              src={footerLogoSrc}
            />
        </div>
        <div className="col-4">
          <p>
            <br />
            Styrelsen for {associationNameFull} kan kontaktas pa foljande satt.
            <br />
            <br />
            E-post: {(variables.ASSOCIATION_EMAIL as string | undefined) ?? ""}
            <br />
            {(variables.ASSOCIATION_OFFICE_HOURS as string | undefined) ?? ""}
          </p>
          <p>
            Adress:
            <br />
            {(variables.ASSOCIATION_ADDRESS_L1 as string | undefined) ?? ""}
            <br />
            {(variables.ASSOCIATION_ADDRESS_L2 as string | undefined) ?? ""}
            <br />
            {(variables.ASSOCIATION_POSTAL_CODE as string | undefined) ?? ""}
          </p>
        </div>
      </div>
      <div className="text-center p-3">&copy; {new Date().getFullYear()}</div>
    </footer>
  );
}
