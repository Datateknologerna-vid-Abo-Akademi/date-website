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
    <div className="reset-password-page">
      <div className="members-form big">
        <h2>Byt lösenord</h2>
        <PasswordResetConfirmForm uid={uid} token={token} />
      </div>
    </div>
  );
}
