import { PasswordResetConfirmForm } from "@/components/members/password-reset-confirm-form";

interface PasswordResetConfirmPageProps {
  params: Promise<{
    uid: string;
    token: string;
  }>;
}

export default async function PasswordResetConfirmPage({ params }: PasswordResetConfirmPageProps) {
  const { uid, token } = await params;

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Set new password</h1>
      </section>
      <section className="panel">
        <PasswordResetConfirmForm uid={uid} token={token} />
      </section>
    </div>
  );
}
