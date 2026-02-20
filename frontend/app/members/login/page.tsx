import Link from "next/link";

import { LoginForm } from "@/components/members/login-form";
import { AuthShell } from "@/components/ui/auth-shell";
import { getSession } from "@/lib/api/queries";

interface LoginPageProps {
  searchParams?: Promise<{
    next?: string;
  }>;
}

function resolveLoginRedirectTarget(target: string | undefined) {
  if (!target) return "/members/profile";
  if (!target.startsWith("/") || target.startsWith("//")) return "/members/profile";
  return target;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const redirectTarget = resolveLoginRedirectTarget(resolvedSearchParams.next);
  const session = await getSession();
  if (session.is_authenticated) {
    return (
      <AuthShell title="Redan inloggad">
        <p>
          Du är redan inloggad.
        </p>
        <p>
          Fortsätt till <Link href={redirectTarget}>din profil</Link>.
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Login" narrow>
      <LoginForm redirectTo={redirectTarget} />
      <Link href="/members/password_reset">
        <p>Glömt lösenordet?</p>
      </Link>
      <Link href="/members/signup">
        <p>Registrera dig</p>
      </Link>
    </AuthShell>
  );
}
