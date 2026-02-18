"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";
import type { CtfGuessResult } from "@/lib/api/types";

interface FlagGuessFormProps {
  ctfSlug: string;
  flagSlug: string;
  canSubmit: boolean;
}

export function FlagGuessForm({ ctfSlug, flagSlug, canSubmit }: FlagGuessFormProps) {
  const [guess, setGuess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    setIsSubmitting(true);
    setErrorMessage("");
    setStatusMessage("");

    try {
      const result = await mutateApi<CtfGuessResult>({
        method: "POST",
        path: `ctf/${ctfSlug}/${flagSlug}/guess`,
        body: { guess },
      });
      setGuess("");
      setStatusMessage(
        result.first_solve ? "Correct flag. You solved it first." : "Correct flag. Already solved.",
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit guess");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Flag guess</span>
        <input
          value={guess}
          onChange={(event) => setGuess(event.target.value)}
          placeholder="flag{...}"
          required
          disabled={!canSubmit || isSubmitting}
        />
      </label>
      <button type="submit" disabled={!canSubmit || isSubmitting}>
        {isSubmitting ? "Submitting..." : "Submit flag"}
      </button>
      {!canSubmit ? <p className="meta">CTF submissions are currently closed.</p> : null}
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
