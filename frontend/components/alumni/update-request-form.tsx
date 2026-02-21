"use client";

import { FormEvent, useState } from "react";

import { useMutation } from "@tanstack/react-query";

import { requestAlumniUpdate } from "@/lib/api/mutations";
import formStyles from "@/components/ui/form-primitives.module.css";


export function AlumniUpdateRequestForm() {
  const [email, setEmail] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const mutation = useMutation({
    mutationFn: ({ email, captchaToken }: { email: string; captchaToken: string }) =>
      requestAlumniUpdate(email, captchaToken),
    onSuccess: () => {
      setStatusMessage("If this email exists in alumni records, a token has been sent.");
      setEmail("");
      setCaptchaToken("");
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Unable to request update token");
    },
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");

    mutation.mutate({ email, captchaToken });
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
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Submitting..." : "Send update link"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
