"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";

interface AlumniSignupResponse {
  submitted: boolean;
  operation: string;
}

interface AlumniSignupState {
  firstname: string;
  lastname: string;
  email: string;
  phone_number: string;
  address: string;
  zip: string;
  city: string;
  country: string;
  year_of_admission: string;
  employer: string;
  work_title: string;
  tfif_membership: string;
  alumni_newsletter_consent: boolean;
  consent: boolean;
  captcha: string;
}

const initialState: AlumniSignupState = {
  firstname: "",
  lastname: "",
  email: "",
  phone_number: "",
  address: "",
  zip: "",
  city: "",
  country: "",
  year_of_admission: "",
  employer: "",
  work_title: "",
  tfif_membership: "vet inte",
  alumni_newsletter_consent: false,
  consent: false,
  captcha: "",
};

export function AlumniSignupForm() {
  const [formState, setFormState] = useState<AlumniSignupState>(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  function updateField<K extends keyof AlumniSignupState>(field: K, value: AlumniSignupState[K]) {
    setFormState((previous) => ({ ...previous, [field]: value }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmitting(true);

    try {
      await mutateApi<AlumniSignupResponse>({
        method: "POST",
        path: "alumni/signup",
        body: {
          operation: "CREATE",
          firstname: formState.firstname,
          lastname: formState.lastname,
          email: formState.email,
          phone_number: formState.phone_number,
          address: formState.address,
          zip: formState.zip,
          city: formState.city,
          country: formState.country,
          year_of_admission: formState.year_of_admission,
          employer: formState.employer,
          work_title: formState.work_title,
          tfif_membership: formState.tfif_membership,
          alumni_newsletter_consent: formState.alumni_newsletter_consent,
          consent: formState.consent,
          "cf-turnstile-response": formState.captcha,
        },
      });
      setFormState(initialState);
      setStatusMessage("Registration submitted. You will receive follow-up by email.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit registration");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <div className="form-grid">
        <label className="form-field">
          <span>First name</span>
          <input
            value={formState.firstname}
            onChange={(event) => updateField("firstname", event.target.value)}
            required
          />
        </label>
        <label className="form-field">
          <span>Last name</span>
          <input
            value={formState.lastname}
            onChange={(event) => updateField("lastname", event.target.value)}
            required
          />
        </label>
      </div>
      <label className="form-field">
        <span>Email</span>
        <input
          type="email"
          value={formState.email}
          onChange={(event) => updateField("email", event.target.value)}
          required
        />
      </label>
      <div className="form-grid">
        <label className="form-field">
          <span>Phone</span>
          <input
            value={formState.phone_number}
            onChange={(event) => updateField("phone_number", event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Year of admission</span>
          <input
            value={formState.year_of_admission}
            onChange={(event) => updateField("year_of_admission", event.target.value)}
          />
        </label>
      </div>
      <label className="form-field">
        <span>Address</span>
        <input
          value={formState.address}
          onChange={(event) => updateField("address", event.target.value)}
        />
      </label>
      <div className="form-grid">
        <label className="form-field">
          <span>Zip</span>
          <input value={formState.zip} onChange={(event) => updateField("zip", event.target.value)} />
        </label>
        <label className="form-field">
          <span>City</span>
          <input value={formState.city} onChange={(event) => updateField("city", event.target.value)} />
        </label>
      </div>
      <label className="form-field">
        <span>Country</span>
        <input value={formState.country} onChange={(event) => updateField("country", event.target.value)} />
      </label>
      <div className="form-grid">
        <label className="form-field">
          <span>Employer</span>
          <input
            value={formState.employer}
            onChange={(event) => updateField("employer", event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Work title</span>
          <input
            value={formState.work_title}
            onChange={(event) => updateField("work_title", event.target.value)}
          />
        </label>
      </div>
      <label className="form-field">
        <span>TFiF membership</span>
        <select
          value={formState.tfif_membership}
          onChange={(event) => updateField("tfif_membership", event.target.value)}
        >
          <option value="ja">Ja</option>
          <option value="nej">Nej</option>
          <option value="vet inte">Vet inte</option>
        </select>
      </label>
      <label className="choice-line">
        <input
          type="checkbox"
          checked={formState.alumni_newsletter_consent}
          onChange={(event) => updateField("alumni_newsletter_consent", event.target.checked)}
        />
        <span>I want alumni event updates.</span>
      </label>
      <label className="form-field">
        <span>Turnstile token (if required by deployment)</span>
        <input
          value={formState.captcha}
          onChange={(event) => updateField("captcha", event.target.value)}
          placeholder="Optional in local development"
        />
      </label>
      <label className="choice-line">
        <input
          type="checkbox"
          checked={formState.consent}
          onChange={(event) => updateField("consent", event.target.checked)}
          required
        />
        <span>I agree to the registration terms.</span>
      </label>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Submit registration"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
