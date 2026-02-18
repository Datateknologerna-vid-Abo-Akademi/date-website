import { activateAccount } from "@/lib/api/queries";

interface ActivationPageProps {
  params: {
    uid: string;
    token: string;
  };
}

export default async function ActivationPage({ params }: ActivationPageProps) {
  const result = await activateAccount(params.uid, params.token).catch(() => null);

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
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
