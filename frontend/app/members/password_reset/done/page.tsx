import styles from "@/features/members/members-page.module.css";

export default function PasswordResetDonePage() {
  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>Password reset request sent</h1>
        <p>If the account exists, a reset email has been sent.</p>
      </section>
    </div>
  );
}
