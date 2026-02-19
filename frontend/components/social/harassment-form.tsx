"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { mutateApi } from "@/lib/api/client";

interface HarassmentFormResponse {
  submitted: boolean;
  id: number;
}

interface HarassmentFormProps {
  captchaSiteKey?: string;
}

declare global {
  interface Window {
    __harassmentTurnstileCallback?: (token: string) => void;
  }
}

export function HarassmentForm({ captchaSiteKey }: HarassmentFormProps) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    window.__harassmentTurnstileCallback = (token: string) => setCaptchaToken(token);
    return () => {
      if (window.__harassmentTurnstileCallback) {
        delete window.__harassmentTurnstileCallback;
      }
    };
  }, []);

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
      setStatusMessage("Anmälan skickad. Tack.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Kunde inte skicka anmälan.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Beskrivning av händelsen *</span>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={6}
          maxLength={1500}
          required
        />
      </label>
      <label className="form-field">
        <span>Ange din e-post om du vill bli kontaktad</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="namn@example.com"
        />
      </label>
      <label className="choice-line">
        <input
          type="checkbox"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
          required
        />
        <span>
          Jag godkänner{" "}
          <Link href="/pages/registerbeskrivning/" target="_blank">
            villkoren
          </Link>
          .
        </span>
      </label>
      {captchaSiteKey ? (
        <div
          className="cf-turnstile"
          data-sitekey={captchaSiteKey}
          data-callback="__harassmentTurnstileCallback"
        />
      ) : null}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Skickar..." : "Skicka"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
