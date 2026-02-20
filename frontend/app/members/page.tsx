import Link from "next/link";

import { getSession } from "@/lib/api/queries";
import styles from "@/features/members/members-page.module.css";

export default async function MembersPage() {
  const session = await getSession();
  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>Member Portal</h1>
        {session.is_authenticated ? (
          <p>Signed in as {session.full_name ?? session.username}.</p>
        ) : (
          <p>You are currently signed out.</p>
        )}
      </section>
      <section className={styles.panel}>
        <div className={styles.linkGrid}>
          {!session.is_authenticated ? <Link href="/members/login">Login</Link> : null}
          {!session.is_authenticated ? <Link href="/members/signup">Signup</Link> : null}
          {!session.is_authenticated ? <Link href="/members/password_reset">Reset password</Link> : null}
          <Link href="/members/profile">Profile</Link>
          <Link href="/members/functionaries">Functionaries</Link>
          <Link href="/members/password_change">Change password</Link>
          <Link href="/members/cert">Certificate</Link>
          <Link href="/polls">Polls</Link>
        </div>
      </section>
    </div>
  );
}
