"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { useMutation } from "@tanstack/react-query";

import { signupUser } from "@/lib/api/mutations";

interface SignupState {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  consent: boolean;
  captchaToken: string;
}

const initialState: SignupState = {
  username: "",
  email: "",
  first_name: "",
  last_name: "",
  password: "",
  consent: false,
  captchaToken: "",
};

interface SignupFormProps {
  captchaSiteKey?: string;
}

declare global {
  interface Window {
    __signupTurnstileCallback?: (token: string) => void;
  }
}

export function SignupForm({ captchaSiteKey }: SignupFormProps) {
  const [formState, setFormState] = useState<SignupState>(initialState);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    window.__signupTurnstileCallback = (token: string) => {
      setFormState((previous) => ({ ...previous, captchaToken: token }));
    };
    return () => {
      if (window.__signupTurnstileCallback) {
        delete window.__signupTurnstileCallback;
      }
    };
  }, []);

  function updateField<K extends keyof SignupState>(field: K, value: SignupState[K]) {
    setFormState((previous) => ({ ...previous, [field]: value }));
  }

  const mutation = useMutation({
    mutationFn: signupUser,
    onSuccess: () => {
      setFormState(initialState);
      setStatusMessage("Registreringen mottogs. Ett admin-konto behöver aktivera användaren.");
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Kunde inte registrera kontot.");
    },
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");

    if (!formState.consent) {
      setErrorMessage("Du måste godkänna villkoren.");
      return;
    }

    mutation.mutate({
      username: formState.username,
      email: formState.email,
      first_name: formState.first_name,
      last_name: formState.last_name,
      password: formState.password,
      "cf-turnstile-response": formState.captchaToken,
    });
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Användarnamn</span>
        <input
          value={formState.username}
          onChange={(event) => updateField("username", event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>Förnamn</span>
        <input
          value={formState.first_name}
          onChange={(event) => updateField("first_name", event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>Efternamn</span>
        <input
          value={formState.last_name}
          onChange={(event) => updateField("last_name", event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>E-post</span>
        <input
          type="email"
          value={formState.email}
          onChange={(event) => updateField("email", event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>Lösenord</span>
        <input
          type="password"
          value={formState.password}
          onChange={(event) => updateField("password", event.target.value)}
          required
        />
      </label>
      <label className="choice-line">
        <input
          type="checkbox"
          checked={formState.consent}
          onChange={(event) => updateField("consent", event.target.checked)}
          required
        />
        <span>
          Jag godkänner{" "}
          <Link href="/p/registerbeskrivning/" target="_blank">
            villkoren
          </Link>
          .
        </span>
      </label>
      {captchaSiteKey ? (
        <div
          className="cf-turnstile"
          data-sitekey={captchaSiteKey}
          data-callback="__signupTurnstileCallback"
        />
      ) : null}
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Skickar..." : "Registrera dig"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
