import { getSession } from "@/lib/api/queries";
import styles from "@/features/members/members-page.module.css";

export default async function MemberCertificatePage() {
  const session = await getSession();
  const now = new Date();

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>Certificate</h1>
        {session.is_authenticated ? (
          <p>
            This certifies that {session.full_name ?? session.username} visited on {now.toLocaleString()}.
          </p>
        ) : (
          <p>Sign in to view your certificate.</p>
        )}
      </section>
    </div>
  );
}
