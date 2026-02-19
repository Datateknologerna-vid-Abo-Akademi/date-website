"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { mutateApi } from "@/lib/api/client";

interface LogoutButtonProps {
  className?: string;
  label?: string;
  redirectTo?: string;
}

export function LogoutButton({
  className,
  label = "Sign out",
  redirectTo = "/members/login",
}: LogoutButtonProps = {}) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  async function onLogout() {
    setIsLoading(true);
    try {
      await mutateApi<{ is_authenticated: boolean }>({
        method: "POST",
        path: "auth/logout",
      });
      router.push(redirectTo);
      router.refresh();
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <button type="button" onClick={onLogout} disabled={isLoading} className={className}>
      {isLoading ? "Signing out..." : label}
    </button>
  );
}
