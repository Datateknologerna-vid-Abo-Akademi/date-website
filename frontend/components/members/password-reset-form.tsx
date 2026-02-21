"use client";

import { FormEvent, useState } from "react";

import { useMutation } from "@tanstack/react-query";

import { resetPassword } from "@/lib/api/mutations";

export function PasswordResetForm() {
  const [email, setEmail] = useState("");
  const mutation = useMutation({
    mutationFn: resetPassword,
    onSuccess: () => {
      setStatusMessage("Om kontot finns har en återställningslänk skickats.");
      setEmail("");
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Kunde inte skicka återställningsbegäran.");
    },
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");

    mutation.mutate({ email });
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
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Skickar..." : "Sänd"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
