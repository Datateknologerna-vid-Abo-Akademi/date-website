"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useMutation } from "@tanstack/react-query";

import { loginUser } from "@/lib/api/mutations";
import styles from "./login-form.module.css";

interface LoginFormProps {
  redirectTo?: string;
}

export function LoginForm({ redirectTo = "/members/profile" }: LoginFormProps) {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: loginUser,
    onSuccess: () => {
      router.push(redirectTo);
      router.refresh();
    },
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate({ username, password });
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
      <button className="button" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "LOGIN..." : "LOGIN"}
      </button>
      {mutation.error ? <p className="form-error">{mutation.error.message}</p> : null}
    </form>
  );
}
