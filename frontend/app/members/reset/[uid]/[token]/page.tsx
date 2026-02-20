import { PasswordResetConfirmForm } from "@/components/members/password-reset-confirm-form";
import { AuthShell } from "@/components/ui/auth-shell";

interface PasswordResetConfirmPageProps {
  params: Promise<{
    uid: string;
    token: string;
  }>;
}

export default async function PasswordResetConfirmPage({ params }: PasswordResetConfirmPageProps) {
  const { uid, token } = await params;

  return (
    <AuthShell title="Byt lösenord">
        <PasswordResetConfirmForm uid={uid} token={token} />
    </AuthShell>
  );
}
