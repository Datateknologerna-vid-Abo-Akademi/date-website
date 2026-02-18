"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";

interface PasswordResetResponse {
  submitted: boolean;
}

export function PasswordResetForm() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmitting(true);

    try {
      await mutateApi<PasswordResetResponse>({
        method: "POST",
        path: "auth/password-reset",
        body: { email },
      });
      setStatusMessage("If the account exists, a reset link has been sent.");
      setEmail("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit password reset request");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Send reset link"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
