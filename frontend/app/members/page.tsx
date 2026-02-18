import Link from "next/link";

import { getSession } from "@/lib/api/queries";

export default async function MembersPage() {
  const session = await getSession();
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Member Portal</h1>
        {session.is_authenticated ? (
          <p>Signed in as {session.full_name ?? session.username}.</p>
        ) : (
          <p>You are currently signed out.</p>
        )}
      </section>
      <section className="panel">
        <div className="link-grid">
          {!session.is_authenticated ? <Link href="/members/login">Login</Link> : null}
          <Link href="/members/profile">Profile</Link>
          <Link href="/members/functionaries">Functionaries</Link>
          <Link href="/polls">Polls</Link>
        </div>
      </section>
    </div>
  );
}
