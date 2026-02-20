import { FunctionaryManager } from "@/components/members/functionary-manager";
import styles from "@/features/members/members-page.module.css";
import { getPublicFunctionaries, getSession } from "@/lib/api/queries";

interface FunctionariesPageProps {
  searchParams: Promise<{
    year?: string;
    role?: string;
  }>;
}

export default async function FunctionariesPage({ searchParams }: FunctionariesPageProps) {
  const resolvedSearchParams = await searchParams;
  const year = resolvedSearchParams.year;
  const role = resolvedSearchParams.role;
  const [session, payload] = await Promise.all([getSession(), getPublicFunctionaries(year, role)]);

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Members</p>
        <h1>Functionaries</h1>
        <p className={styles.meta}>
          Filter: year={year ?? "current"} role={role ?? "all"}
        </p>
      </section>

      {session.is_authenticated ? (
        <section className={styles.panel}>
          <h2>Manage your functionary roles</h2>
          <FunctionaryManager initialYear={new Date().getFullYear()} />
        </section>
      ) : null}

      <section className={styles.panel}>
        <h2>Board roles</h2>
        <div className={styles.roleGrid}>
          {Object.entries(payload.board_functionaries_by_role).map(([roleName, functionaries]) => (
            <article key={roleName}>
              <h3>{roleName}</h3>
              <ul className={styles.list}>
                {functionaries.map((functionary) => (
                  <li key={functionary.id}>
                    {functionary.member_name} ({functionary.year})
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.panel}>
        <h2>Other roles</h2>
        <div className={styles.roleGrid}>
          {Object.entries(payload.functionaries_by_role).map(([roleName, functionaries]) => (
            <article key={roleName}>
              <h3>{roleName}</h3>
              <ul className={styles.list}>
                {functionaries.map((functionary) => (
                  <li key={functionary.id}>
                    {functionary.member_name} ({functionary.year})
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
