import { PasswordResetConfirmForm } from "@/components/members/password-reset-confirm-form";

interface PasswordResetConfirmPageProps {
  params: {
    uid: string;
    token: string;
  };
}

export default function PasswordResetConfirmPage({ params }: PasswordResetConfirmPageProps) {
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Set new password</h1>
      </section>
      <section className="panel">
        <PasswordResetConfirmForm uid={params.uid} token={params.token} />
      </section>
    </div>
  );
}
