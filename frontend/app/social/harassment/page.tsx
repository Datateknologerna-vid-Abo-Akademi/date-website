import { HarassmentForm } from "@/components/social/harassment-form";

export default function HarassmentPage() {
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Social</p>
        <h1>Report Harassment</h1>
        <p>You can submit anonymously or include your email for follow-up.</p>
      </section>
      <section className="panel">
        <HarassmentForm />
      </section>
    </div>
  );
}
