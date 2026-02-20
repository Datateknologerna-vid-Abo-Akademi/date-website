import styles from "@/features/members/members-page.module.css";

export default function PasswordResetCompletePage() {
  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>Password updated</h1>
        <p>You can now sign in with your new password.</p>
      </section>
    </div>
  );
}
