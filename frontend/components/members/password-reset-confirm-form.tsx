"use client";

import { FormEvent, useState } from "react";

import { useMutation } from "@tanstack/react-query";

import { PasswordResetConfirmPayload, confirmPasswordReset } from "@/lib/api/mutations";


interface PasswordResetConfirmFormProps {
  uid: string;
  token: string;
}

export function PasswordResetConfirmForm({ uid, token }: PasswordResetConfirmFormProps) {
  const [newPassword1, setNewPassword1] = useState("");
  const [newPassword2, setNewPassword2] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const mutation = useMutation({
    mutationFn: (variables: { uid: string; token: string; payload: PasswordResetConfirmPayload }) =>
      confirmPasswordReset(variables.uid, variables.token, variables.payload),
    onSuccess: () => {
      setStatusMessage("Lösenordet har uppdaterats.");
      setNewPassword1("");
      setNewPassword2("");
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Kunde inte byta lösenord.");
    },
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");

    mutation.mutate({
      uid,
      token,
      payload: {
        new_password1: newPassword1,
        new_password2: newPassword2,
      },
    });
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Nytt lösenord</span>
        <input
          type="password"
          value={newPassword1}
          onChange={(event) => setNewPassword1(event.target.value)}
          required
        />
      </label>
      <label className="form-field">
        <span>Upprepa nytt lösenord</span>
        <input
          type="password"
          value={newPassword2}
          onChange={(event) => setNewPassword2(event.target.value)}
          required
        />
      </label>
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Skickar..." : "Byt lösenord"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
