"use client";

import { FormEvent, useMemo, useState } from "react";

import { mutateApi } from "@/lib/api/client";
import type { MemberProfile } from "@/lib/api/types";

interface ProfileFormProps {
  profile: MemberProfile;
}

interface ProfileFormState {
  first_name: string;
  last_name: string;
  phone: string;
  address: string;
  zip_code: string;
  city: string;
  country: string;
}

export function ProfileForm({ profile }: ProfileFormProps) {
  const initialState = useMemo<ProfileFormState>(
    () => ({
      first_name: profile.first_name ?? "",
      last_name: profile.last_name ?? "",
      phone: profile.phone ?? "",
      address: profile.address ?? "",
      zip_code: profile.zip_code ?? "",
      city: profile.city ?? "",
      country: profile.country ?? "",
    }),
    [profile],
  );

  const [formState, setFormState] = useState(initialState);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  function updateField(field: keyof ProfileFormState, value: string) {
    setFormState((previous) => ({ ...previous, [field]: value }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSaving(true);
    try {
      await mutateApi<MemberProfile>({
        method: "PATCH",
        path: "members/me",
        body: formState,
      });
      setStatusMessage("Profile updated.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update profile");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={onSubmit}>
      <div className="form-grid">
        <label className="form-field">
          <span>First name</span>
          <input
            value={formState.first_name}
            onChange={(event) => updateField("first_name", event.target.value)}
            required
          />
        </label>
        <label className="form-field">
          <span>Last name</span>
          <input
            value={formState.last_name}
            onChange={(event) => updateField("last_name", event.target.value)}
            required
          />
        </label>
      </div>
      <label className="form-field">
        <span>Phone</span>
        <input value={formState.phone} onChange={(event) => updateField("phone", event.target.value)} />
      </label>
      <label className="form-field">
        <span>Address</span>
        <input value={formState.address} onChange={(event) => updateField("address", event.target.value)} />
      </label>
      <div className="form-grid">
        <label className="form-field">
          <span>Zip code</span>
          <input value={formState.zip_code} onChange={(event) => updateField("zip_code", event.target.value)} />
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
      <button type="submit" disabled={isSaving}>
        {isSaving ? "Saving..." : "Save profile"}
      </button>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
    </form>
  );
}
