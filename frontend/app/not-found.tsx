import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">404</p>
        <h1>Page not found</h1>
        <p>The requested resource does not exist in the decoupled frontend route set.</p>
        <Link href="/" className="cta-link">
          Return home
        </Link>
      </section>
    </div>
  );
}
