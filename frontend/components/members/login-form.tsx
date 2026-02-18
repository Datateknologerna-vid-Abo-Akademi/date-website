"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";

export function LoginForm() {
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
      router.push("/members/profile");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Username or email</span>
        <input value={username} onChange={(event) => setUsername(event.target.value)} required />
      </label>
      <label className="form-field">
        <span>Password</span>
        <input
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          required
        />
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in..." : "Sign in"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
    </form>
  );
}
