"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";
import formStyles from "@/components/ui/form-primitives.module.css";

interface AlumniUpdateRequestResponse {
  submitted: boolean;
}

export function AlumniUpdateRequestForm() {
  const [email, setEmail] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmitting(true);

    try {
      await mutateApi<AlumniUpdateRequestResponse>({
        method: "POST",
        path: "alumni/update",
        body: {
          email,
          "cf-turnstile-response": captchaToken,
        },
      });
      setStatusMessage("If this email exists in alumni records, a token has been sent.");
      setEmail("");
      setCaptchaToken("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to request update token");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className={formStyles.stack} onSubmit={onSubmit}>
      <label className={formStyles.field}>
        <span>Email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </label>
      <label className={formStyles.field}>
        <span>Turnstile token (if required by deployment)</span>
        <input
          value={captchaToken}
          onChange={(event) => setCaptchaToken(event.target.value)}
          placeholder="Optional in local development"
        />
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Send update link"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
