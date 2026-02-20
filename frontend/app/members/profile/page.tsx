import Link from "next/link";
import { notFound } from "next/navigation";

import { LogoutButton } from "@/components/members/logout-button";
import { ProfileForm } from "@/components/members/profile-form";
import styles from "@/features/members/members-page.module.css";
import { getMemberProfile, getSession } from "@/lib/api/queries";

export default async function ProfilePage() {
  const session = await getSession();
  if (!session.is_authenticated)
    return (
      <div className={styles.shell}>
        <section className={styles.hero}>
          <p className={styles.eyebrow}>Members</p>
          <h1>Sign in required</h1>
          <p>
            Please <Link href="/members/login">sign in</Link> to view your profile.
          </p>
        </section>
      </div>
    );

  const profile = await getMemberProfile().catch(() => null);
  if (!profile) {
    notFound();
  }

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>{profile.first_name || profile.username}</h1>
        <p className={styles.meta}>
          {profile.email} - Membership: {profile.membership_type}
          {profile.active_subscription ? ` - Active: ${profile.active_subscription}` : ""}
        </p>
      </section>
      <section className={styles.panel}>
        <ProfileForm profile={profile} />
      </section>
      <section className={styles.panel}>
        <LogoutButton />
      </section>
    </div>
  );
}
