import Script from "next/script";

import { SignupForm } from "@/components/members/signup-form";
import { getSiteMeta } from "@/lib/api/queries";

export default async function MemberSignupPage() {
  const siteMeta = await getSiteMeta();
  const captchaSiteKey = siteMeta.captcha_site_key || "";

  return (
    <div className="signup-page">
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="afterInteractive"
      />
      <div className="members-form big">
        <h2>Registrera dig</h2>
        <SignupForm captchaSiteKey={captchaSiteKey} />
      </div>
    </div>
  );
}
