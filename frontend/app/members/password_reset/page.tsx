import { PasswordResetForm } from "@/components/members/password-reset-form";
import { AuthShell } from "@/components/ui/auth-shell";

export default function PasswordResetPage() {
  return (
    <AuthShell title="Glömt lösenord">
        <PasswordResetForm />
    </AuthShell>
  );
}
