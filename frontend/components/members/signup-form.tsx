"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";

interface SignupResponse {
  registered: boolean;
  username: string;
  requires_activation: boolean;
}

interface SignupState {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  captchaToken: string;
}

const initialState: SignupState = {
  username: "",
  email: "",
  first_name: "",
  last_name: "",
  password: "",
  captchaToken: "",
};

export function SignupForm() {
  const [formState, setFormState] = useState<SignupState>(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  function updateField<K extends keyof SignupState>(field: K, value: SignupState[K]) {
    setFormState((previous) => ({ ...previous, [field]: value }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmitting(true);

    try {
      await mutateApi<SignupResponse>({
        method: "POST",
        path: "auth/signup",
        body: {
          username: formState.username,
          email: formState.email,
          first_name: formState.first_name,
          last_name: formState.last_name,
          password: formState.password,
          "cf-turnstile-response": formState.captchaToken,
        },
      });
      setFormState(initialState);
      setStatusMessage("Signup submitted. An administrator must activate your account.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to sign up");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Username</span>
        <input
          value={formState.username}
          onChange={(event) => updateField("username", event.target.value)}
          required
        />
      </label>
      <div className="form-grid">
        <label className="form-field">
          <span>First name</span>
          <input
            value={formState.first_name}
            onChange={(event) => updateField("first_name", event.target.value)}
            required
          />
        </label>
        <label className="form-field">
          <span>Last name</span>
          <input
            value={formState.last_name}
            onChange={(event) => updateField("last_name", event.target.value)}
            required
          />
        </label>
      </div>
      <label className="form-field">
        <span>Email</span>
        <input
          type="email"
          value={formState.email}
          onChange={(event) => updateField("email", event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>Password</span>
        <input
          type="password"
          value={formState.password}
          onChange={(event) => updateField("password", event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>Turnstile token (if captcha is enabled)</span>
        <input
          value={formState.captchaToken}
          onChange={(event) => updateField("captchaToken", event.target.value)}
          placeholder="Optional in local development"
        />
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Create account"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
