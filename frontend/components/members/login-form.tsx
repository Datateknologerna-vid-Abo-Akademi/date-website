"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";
import styles from "./login-form.module.css";

interface LoginFormProps {
  redirectTo?: string;
}

export function LoginForm({ redirectTo = "/members/profile" }: LoginFormProps) {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);
    try {
      await mutateApi<{ is_authenticated: boolean; username: string }>({
        method: "POST",
        path: "auth/login",
        body: { username, password },
      });
      router.push(redirectTo);
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Inloggning misslyckades.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <p>
        <label htmlFor="login-username">Användarnamn</label>
        <input
          id="login-username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
        />
      </p>
      <p>
        <label htmlFor="login-password">Lösenord</label>
        <input
          id="login-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          required
        />
      </p>
      <button className="button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "LOGIN..." : "LOGIN"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
    </form>
  );
}
