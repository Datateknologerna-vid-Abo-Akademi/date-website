"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { mutateApi } from "@/lib/api/client";

export function LogoutButton() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  async function onLogout() {
    setIsLoading(true);
    try {
      await mutateApi<{ is_authenticated: boolean }>({
        method: "POST",
        path: "auth/logout",
      });
      router.push("/members/login");
      router.refresh();
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <button type="button" onClick={onLogout} disabled={isLoading}>
      {isLoading ? "Signing out..." : "Sign out"}
    </button>
  );
}
