import styles from "@/features/members/members-page.module.css";

export default function PasswordChangeDonePage() {
  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>Password changed</h1>
      </section>
    </div>
  );
}
