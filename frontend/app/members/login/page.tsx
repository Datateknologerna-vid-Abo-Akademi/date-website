import Link from "next/link";

import { LoginForm } from "@/components/members/login-form";
import { getSession } from "@/lib/api/queries";

export default async function LoginPage() {
  const session = await getSession();
  if (session.is_authenticated)
    return (
      <div className="page-shell">
        <section className="hero compact">
          <p className="eyebrow">Members</p>
          <h1>Already signed in</h1>
          <p>
            Continue to <Link href="/members/profile">your profile</Link>.
          </p>
        </section>
      </div>
    );

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Sign in</h1>
      </section>
      <section className="panel">
        <LoginForm />
        <div className="link-grid">
          <Link href="/members/signup">Create account</Link>
          <Link href="/members/password_reset">Forgot password</Link>
        </div>
      </section>
    </div>
  );
}
