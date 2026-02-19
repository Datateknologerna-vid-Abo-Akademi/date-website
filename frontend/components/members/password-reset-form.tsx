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
      setStatusMessage("Om kontot finns har en återställningslänk skickats.");
      setEmail("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Kunde inte skicka återställningsbegäran.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>E-post</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Skickar..." : "Sänd"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
