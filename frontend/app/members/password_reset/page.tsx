import { PasswordResetForm } from "@/components/members/password-reset-form";

export default function PasswordResetPage() {
  return (
    <div className="forgot-password-page">
      <div className="members-form big">
        <h2>Glömt lösenord</h2>
        <PasswordResetForm />
      </div>
    </div>
  );
}
