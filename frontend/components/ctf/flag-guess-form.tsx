"use client";

import { FormEvent, useState } from "react";

import { useMutation } from "@tanstack/react-query";

import { guessCtfFlag } from "@/lib/api/mutations";
import type { CtfGuessResult } from "@/lib/api/types";
import formStyles from "@/components/ui/form-primitives.module.css";

interface FlagGuessFormProps {
  ctfSlug: string;
  flagSlug: string;
  canSubmit: boolean;
}

export function FlagGuessForm({ ctfSlug, flagSlug, canSubmit }: FlagGuessFormProps) {
  const [guess, setGuess] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  const mutation = useMutation({
    mutationFn: (variables: { ctfSlug: string; flagSlug: string; guess: string }) =>
      guessCtfFlag(variables.ctfSlug, variables.flagSlug, variables.guess),
    onSuccess: (result: unknown) => {
      setGuess("");
      setStatusMessage(
        (result as CtfGuessResult).first_solve
          ? "Correct flag. You solved it first."
          : "Correct flag. Already solved.",
      );
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit guess");
    },
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    setErrorMessage("");
    setStatusMessage("");

    mutation.mutate({ ctfSlug, flagSlug, guess });
  }

  return (
    <form className={formStyles.stack} onSubmit={onSubmit}>
      <label className={formStyles.field}>
        <span>Flag guess</span>
        <input
          value={guess}
          onChange={(event) => setGuess(event.target.value)}
          placeholder="flag{...}"
          required
          disabled={!canSubmit || mutation.isPending}
        />
      </label>
      <button type="submit" disabled={!canSubmit || mutation.isPending}>
        {mutation.isPending ? "Submitting..." : "Submit flag"}
      </button>
      {!canSubmit ? <p className="meta">CTF submissions are currently closed.</p> : null}
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
