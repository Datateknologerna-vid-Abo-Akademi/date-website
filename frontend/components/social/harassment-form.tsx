"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";

interface HarassmentFormResponse {
  submitted: boolean;
  id: number;
}

export function HarassmentForm() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
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
      await mutateApi<HarassmentFormResponse>({
        method: "POST",
        path: "social/harassment",
        body: {
          email,
          message,
          consent,
          "cf-turnstile-response": captchaToken,
        },
      });
      setMessage("");
      setEmail("");
      setConsent(false);
      setCaptchaToken("");
      setStatusMessage("Report submitted. Thank you.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit report");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Describe the incident</span>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={6}
          maxLength={1500}
          required
        />
      </label>
      <label className="form-field">
        <span>Email (optional)</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="name@example.com"
        />
      </label>
      <label className="form-field">
        <span>Turnstile token (if required by deployment)</span>
        <input
          value={captchaToken}
          onChange={(event) => setCaptchaToken(event.target.value)}
          placeholder="Optional in local development"
        />
      </label>
      <label className="choice-line">
        <input
          type="checkbox"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
          required
        />
        <span>I agree to the reporting terms.</span>
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Submit report"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
