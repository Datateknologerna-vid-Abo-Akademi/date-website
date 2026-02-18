import { FunctionaryManager } from "@/components/members/functionary-manager";
import { getPublicFunctionaries, getSession } from "@/lib/api/queries";

interface FunctionariesPageProps {
  searchParams: {
    year?: string;
    role?: string;
  };
}

export default async function FunctionariesPage({ searchParams }: FunctionariesPageProps) {
  const year = searchParams.year;
  const role = searchParams.role;
  const [session, payload] = await Promise.all([getSession(), getPublicFunctionaries(year, role)]);

  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Functionaries</h1>
        <p className="meta">
          Filter: year={year ?? "current"} role={role ?? "all"}
        </p>
      </section>

      {session.is_authenticated ? (
        <section className="panel">
          <h2>Manage your functionary roles</h2>
          <FunctionaryManager initialYear={new Date().getFullYear()} />
        </section>
      ) : null}

      <section className="panel">
        <h2>Board roles</h2>
        <div className="role-grid">
          {Object.entries(payload.board_functionaries_by_role).map(([roleName, functionaries]) => (
            <article key={roleName}>
              <h3>{roleName}</h3>
              <ul className="list">
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

      <section className="panel">
        <h2>Other roles</h2>
        <div className="role-grid">
          {Object.entries(payload.functionaries_by_role).map(([roleName, functionaries]) => (
            <article key={roleName}>
              <h3>{roleName}</h3>
              <ul className="list">
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
