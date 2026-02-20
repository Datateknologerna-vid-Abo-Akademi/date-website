import { activateAccount } from "@/lib/api/queries";
import styles from "@/features/members/members-page.module.css";

interface ActivationPageProps {
  params: Promise<{
    uid: string;
    token: string;
  }>;
}

export default async function ActivationPage({ params }: ActivationPageProps) {
  const { uid, token } = await params;
  const result = await activateAccount(uid, token).catch(() => null);

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>{result ? "Account activated" : "Activation failed"}</h1>
        <p>
          {result
            ? `User ${result.username} is now active.`
            : "Activation link is invalid or expired."}
        </p>
      </section>
    </div>
  );
}
