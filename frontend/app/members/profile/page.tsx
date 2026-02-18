import Link from "next/link";
import { notFound } from "next/navigation";

import { LogoutButton } from "@/components/members/logout-button";
import { ProfileForm } from "@/components/members/profile-form";
import { getMemberProfile, getSession } from "@/lib/api/queries";

export default async function ProfilePage() {
  const session = await getSession();
  if (!session.is_authenticated)
    return (
      <div className="page-shell">
        <section className="hero compact">
          <p className="eyebrow">Members</p>
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
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>{profile.first_name || profile.username}</h1>
        <p className="meta">
          {profile.email} - Membership: {profile.membership_type}
          {profile.active_subscription ? ` - Active: ${profile.active_subscription}` : ""}
        </p>
      </section>
      <section className="panel">
        <ProfileForm profile={profile} />
      </section>
      <section className="panel">
        <LogoutButton />
      </section>
    </div>
  );
}
