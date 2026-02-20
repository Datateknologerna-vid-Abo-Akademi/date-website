import { PasswordChangeForm } from "@/components/members/password-change-form";
import styles from "@/features/members/members-page.module.css";
import { getSession } from "@/lib/api/queries";

export default async function PasswordChangePage() {
  const session = await getSession();

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>Change password</h1>
      </section>
      <section className={styles.panel}>
        {session.is_authenticated ? (
          <PasswordChangeForm />
        ) : (
          <p>You must sign in before changing password.</p>
        )}
      </section>
    </div>
  );
}
