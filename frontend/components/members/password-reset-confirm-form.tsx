"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";

interface PasswordResetConfirmResponse {
  password_reset: boolean;
}

interface PasswordResetConfirmFormProps {
  uid: string;
  token: string;
}

export function PasswordResetConfirmForm({ uid, token }: PasswordResetConfirmFormProps) {
  const [newPassword1, setNewPassword1] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmitting(true);

    try {
      await mutateApi<PasswordResetConfirmResponse>({
        method: "POST",
        path: `auth/password-reset/${uid}/${token}`,
        body: {
          new_password1: newPassword1,
          new_password2: newPassword2,
        },
      });
      setStatusMessage("Password reset successful.");
      setNewPassword1("");
      setNewPassword2("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to reset password");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>New password</span>
        <input
          type="password"
          value={newPassword1}
          onChange={(event) => setNewPassword1(event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>Repeat new password</span>
        <input
          type="password"
          value={newPassword2}
          onChange={(event) => setNewPassword2(event.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Reset password"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
