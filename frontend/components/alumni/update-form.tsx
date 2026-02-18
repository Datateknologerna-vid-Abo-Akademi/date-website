"use client";

import { FormEvent, useState } from "react";

import { mutateApi } from "@/lib/api/client";

interface AlumniUpdateFormProps {
  email: string;
  token: string;
}

interface AlumniUpdateResponse {
  updated: boolean;
}

interface AlumniUpdateState {
  firstname: string;
  lastname: string;
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
}

const initialState: AlumniUpdateState = {
  firstname: "",
  lastname: "",
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
};

export function AlumniUpdateForm({ email, token }: AlumniUpdateFormProps) {
  const [formState, setFormState] = useState<AlumniUpdateState>(initialState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  function updateField<K extends keyof AlumniUpdateState>(field: K, value: AlumniUpdateState[K]) {
    setFormState((previous) => ({ ...previous, [field]: value }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmitting(true);

    try {
      await mutateApi<AlumniUpdateResponse>({
        method: "POST",
        path: `alumni/update/${token}`,
        body: {
          ...formState,
        },
      });
      setStatusMessage("Your alumni information has been queued for update.");
      setFormState(initialState);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update alumni information");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <label className="form-field">
        <span>Email</span>
        <input value={email} disabled />
      </label>
      <div className="form-grid">
        <label className="form-field">
          <span>First name</span>
          <input
            value={formState.firstname}
            onChange={(event) => updateField("firstname", event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>Last name</span>
          <input
            value={formState.lastname}
            onChange={(event) => updateField("lastname", event.target.value)}
          />
        </label>
      </div>
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
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Submit update"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
