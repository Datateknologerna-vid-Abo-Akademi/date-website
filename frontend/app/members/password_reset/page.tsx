import { PasswordResetForm } from "@/components/members/password-reset-form";

export default function PasswordResetPage() {
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Reset password</h1>
      </section>
      <section className="panel">
        <PasswordResetForm />
      </section>
    </div>
  );
}
