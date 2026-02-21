"use client";

import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";

import { logoutUser } from "@/lib/api/mutations";

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
  const mutation = useMutation({
    mutationFn: logoutUser,
    onSuccess: () => {
      router.push(redirectTo);
      router.refresh();
    },
  });

  async function onLogout() {
    mutation.mutate();
  }

  return (
    <button type="button" onClick={onLogout} disabled={mutation.isPending} className={className}>
      {mutation.isPending ? "Signing out..." : label}
    </button>
  );
}
