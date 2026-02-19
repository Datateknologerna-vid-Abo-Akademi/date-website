import { SignupForm } from "@/components/members/signup-form";

export default function MemberSignupPage() {
  return (
    <div className="page-shell">
      <section className="hero compact">
        <p className="eyebrow">Members</p>
        <h1>Create account</h1>
      </section>
      <section className="panel">
        <SignupForm />
      </section>
    </div>
  );
}
