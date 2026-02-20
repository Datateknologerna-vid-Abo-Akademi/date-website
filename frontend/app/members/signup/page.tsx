import Script from "next/script";

import { SignupForm } from "@/components/members/signup-form";
import { AuthShell } from "@/components/ui/auth-shell";
import { getSiteMeta } from "@/lib/api/queries";

export default async function MemberSignupPage() {
  const siteMeta = await getSiteMeta();
  const captchaSiteKey = siteMeta.captcha_site_key || "";

  return (
    <>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="afterInteractive"
      />
      <AuthShell title="Registrera dig">
        <SignupForm captchaSiteKey={captchaSiteKey} />
      </AuthShell>
    </>
  );
}
