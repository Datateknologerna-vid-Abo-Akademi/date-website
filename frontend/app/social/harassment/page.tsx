import Script from "next/script";

import { HarassmentForm } from "@/components/social/harassment-form";
import { ContentPanel } from "@/components/ui/content-panel";
import { getSiteMeta } from "@/lib/api/queries";
import { ensureModuleEnabled } from "@/lib/module-guards";
import styles from "@/features/social/harassment-page.module.css";

function getContentVariable(contentVariables: Record<string, unknown>, key: string, fallback: string) {
  const value = contentVariables[key];
  if (typeof value === "string" && value.trim()) return value;
  return fallback;
}

export default async function HarassmentPage() {
  await ensureModuleEnabled("social");
  const siteMeta = await getSiteMeta();
  const associationName = getContentVariable(siteMeta.content_variables, "ASSOCIATION_NAME", "föreningen");
  const associationNameShort = getContentVariable(
    siteMeta.content_variables,
    "ASSOCIATION_NAME_SHORT",
    associationName,
  );
  const captchaSiteKey = siteMeta.captcha_site_key || "";

  return (
    <div className={styles.shell}>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="afterInteractive"
      />
      <div className={styles.inner}>
        <ContentPanel>
          <h1>Rapportera trakasserier och eventuella brister med jämlikhetsplanen</h1>
          <p>
            Du kan rapportera trakasserier och brister i jämlikhetsplanen antingen anonymt eller
            ange din kontaktinformation. Vi tar alla former av trakasserier på allvar och kommer
            att vidta åtgärder för att upprätthålla en trygg och respektfull miljö för alla
            medlemmar.
            <br />
            <br />
            {associationName}s trygghetspersoner behandlar alla rapporteringar av trakasserier och
            tar kontakt till {associationNameShort}s styrelse och/eller ÅAS trakasseriombud om det
            så önskas.
          </p>
          <HarassmentForm captchaSiteKey={captchaSiteKey} />
        </ContentPanel>
      </div>
    </div>
  );
}
