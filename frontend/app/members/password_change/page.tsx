import { PasswordChangeForm } from "@/components/members/password-change-form";
import { getSession } from "@/lib/api/queries";

export default async function PasswordChangePage() {
  const session = await getSession();

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Change password</h1>
      </section>
      <section className="panel">
        {session.is_authenticated ? (
          <PasswordChangeForm />
        ) : (
          <p>You must sign in before changing password.</p>
        )}
      </section>
    </div>
  );
}
