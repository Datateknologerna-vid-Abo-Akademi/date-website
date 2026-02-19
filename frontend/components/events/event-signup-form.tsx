"use client";

import { Dispatch, FormEvent, SetStateAction, useMemo, useState } from "react";

import { mutateApi } from "@/lib/api/client";
import type { EventItem, EventSignupBilling, EventSignupResult } from "@/lib/api/types";

interface EventSignupFormProps {
  event: EventItem;
}

type DynamicValue = string | boolean;
type DynamicField = EventItem["sign_up_fields"][number];

function buildDynamicDefaults(fields: DynamicField[]) {
  const defaults: Record<string, DynamicValue> = {};
  fields.forEach((field) => {
    defaults[field.name] = field.type === "checkbox" ? false : "";
  });
  return defaults;
}

function billingStatusLabel(billing: EventSignupBilling) {
  if (!billing.enabled) return "Fakturering är inte aktiv för detta evenemang.";
  if (billing.status === "invoice_created") return "Faktura skapad och skickad via e-post.";
  if (billing.status === "not_configured") return "Ingen faktureringskonfiguration hittades för evenemanget.";
  if (billing.status === "no_invoice_generated") return "Ingen faktura skapades för denna anmälning.";
  if (billing.status === "already_registered") return "En anmälning finns redan för denna e-postadress.";
  if (billing.status === "processing_error") return "Fakturering misslyckades efter anmälan. Kontakta arrangören.";
  return "Fakturering behandlad.";
}

export function EventSignupForm({ event }: EventSignupFormProps) {
  const [passcode, setPasscode] = useState("");
  const [passcodeVerified, setPasscodeVerified] = useState(Boolean(event.passcode_verified));
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [withAvec, setWithAvec] = useState(false);
  const [avecName, setAvecName] = useState("");
  const [avecEmail, setAvecEmail] = useState("");
  const [avecAnonymous, setAvecAnonymous] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [dynamicValues, setDynamicValues] = useState<Record<string, DynamicValue>>(
    () => buildDynamicDefaults(event.sign_up_fields),
  );
  const [avecDynamicValues, setAvecDynamicValues] = useState<Record<string, DynamicValue>>(
    () => buildDynamicDefaults(event.sign_up_fields.filter((field) => !field.hide_for_avec)),
  );
  const [isSubmittingPasscode, setIsSubmittingPasscode] = useState(false);
  const [isSubmittingSignup, setIsSubmittingSignup] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [signupResult, setSignupResult] = useState<EventSignupResult | null>(null);

  const requiresPasscode = Boolean(event.passcode_required) && !passcodeVerified;
  const signupOpen = useMemo(() => {
    if (!event.sign_up || event.event_full || event.registration_past_due) return false;
    return event.registration_open_members || event.registration_open_others;
  }, [event]);

  function renderDynamicField(
    field: DynamicField,
    values: Record<string, DynamicValue>,
    setValues: Dispatch<SetStateAction<Record<string, DynamicValue>>>,
    prefix = "",
  ) {
    const fieldId = `${prefix}${field.name}`;
    const currentValue = values[field.name];
    if (field.type === "select") {
      return (
        <label className="form-field" key={fieldId}>
          <span>{field.name}</span>
          <select
            value={typeof currentValue === "string" ? currentValue : ""}
            required={field.required}
            onChange={(eventTarget) =>
              setValues((previous) => ({ ...previous, [field.name]: eventTarget.target.value }))
            }
          >
            <option value="">Välj ett alternativ</option>
            {field.choices.map((choice) => (
              <option key={`${fieldId}-${choice}`} value={choice}>
                {choice}
              </option>
            ))}
          </select>
        </label>
      );
    }
    if (field.type === "checkbox") {
      return (
        <label className="choice-line" key={fieldId}>
          <input
            type="checkbox"
            checked={Boolean(currentValue)}
            required={field.required}
            onChange={(eventTarget) =>
              setValues((previous) => ({ ...previous, [field.name]: eventTarget.target.checked }))
            }
          />
          <span>{field.name}</span>
        </label>
      );
    }
    return (
      <label className="form-field" key={fieldId}>
        <span>{field.name}</span>
        <input
          value={typeof currentValue === "string" ? currentValue : ""}
          required={field.required}
          onChange={(eventTarget) =>
            setValues((previous) => ({ ...previous, [field.name]: eventTarget.target.value }))
          }
        />
      </label>
    );
  }

  async function onSubmitPasscode(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmittingPasscode(true);
    try {
      const response = await mutateApi<{ passcode_verified: boolean }>({
        method: "POST",
        path: `events/${event.slug}/passcode`,
        body: { passcode },
      });
      if (response.passcode_verified) {
        setPasscodeVerified(true);
        setPasscode("");
        setStatusMessage("Passcode verifierad.");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Verifiering av passcode misslyckades");
    } finally {
      setIsSubmittingPasscode(false);
    }
  }

  async function onSubmitSignup(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    setErrorMessage("");
    setStatusMessage("");
    setIsSubmittingSignup(true);

    const payload: Record<string, DynamicValue> = {
      user: name,
      email,
      anonymous,
      ...dynamicValues,
    };

    if (event.sign_up_avec) {
      payload.avec = withAvec;
      if (withAvec) {
        payload.avec_user = avecName;
        payload.avec_email = avecEmail;
        payload.avec_anonymous = avecAnonymous;
        Object.entries(avecDynamicValues).forEach(([key, value]) => {
          payload[`avec_${key}`] = value;
        });
      }
    }

    if (event.captcha) {
      payload["cf-turnstile-response"] = captchaToken;
    }

    try {
      const response = await mutateApi<EventSignupResult>({
        method: "POST",
        path: `events/${event.slug}/signup`,
        body: payload,
      });
      setSignupResult(response);
      setStatusMessage("Anmälning registrerad.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Anmälning misslyckades");
    } finally {
      setIsSubmittingSignup(false);
    }
  }

  if (!event.sign_up) {
    return <p className="meta">Anmälning är inte aktiv för detta evenemang.</p>;
  }

  if (requiresPasscode) {
    return (
      <form className="form event-signup-form" id="passcode-form" onSubmit={onSubmitPasscode}>
        <label className="form-field">
          <span>Passcode</span>
          <input
            value={passcode}
            onChange={(eventTarget) => setPasscode(eventTarget.target.value)}
            required
          />
        </label>
        <button className="button" type="submit" disabled={isSubmittingPasscode}>
          {isSubmittingPasscode ? "Verifierar..." : "Skicka"}
        </button>
        {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
        {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
      </form>
    );
  }

  if (!signupOpen) {
    return <p className="meta">Anmälningen är stängd just nu.</p>;
  }

  return (
    <div className="form-stack event-signup-wrapper">
      <p className="meta">OBS! Anmälningen är bindande om inget annat meddelas.</p>
      <form className="form event-signup-form" id="attend-form" onSubmit={onSubmitSignup}>
        <div className="form-grid">
          <label className="form-field">
            <span>Namn</span>
            <input value={name} onChange={(eventTarget) => setName(eventTarget.target.value)} required />
          </label>
          <label className="form-field">
            <span>E-post</span>
            <input
              type="email"
              value={email}
              onChange={(eventTarget) => setEmail(eventTarget.target.value)}
              required
            />
          </label>
        </div>
        <label className="choice-line">
          <input
            type="checkbox"
            checked={anonymous}
            onChange={(eventTarget) => setAnonymous(eventTarget.target.checked)}
          />
          <span>Anonym i deltagarlistan</span>
        </label>

        {event.sign_up_fields.length > 0 ? (
          <fieldset className="form-fieldset">
            <legend>Anmälningsdetaljer</legend>
            {event.sign_up_fields.map((field) =>
              renderDynamicField(field, dynamicValues, setDynamicValues, "event-"),
            )}
          </fieldset>
        ) : null}

        {event.sign_up_avec ? (
          <fieldset className="form-fieldset">
            <legend>Avec</legend>
            <label className="choice-line">
              <input
                type="checkbox"
                checked={withAvec}
                onChange={(eventTarget) => setWithAvec(eventTarget.target.checked)}
              />
              <span>Anmäl med avec</span>
            </label>
            {withAvec ? (
              <div className="form-stack">
                <div className="form-grid">
                  <label className="form-field">
                    <span>Avec namn</span>
                    <input
                      value={avecName}
                      onChange={(eventTarget) => setAvecName(eventTarget.target.value)}
                      required
                    />
                  </label>
                  <label className="form-field">
                    <span>Avec e-post</span>
                    <input
                      type="email"
                      value={avecEmail}
                      onChange={(eventTarget) => setAvecEmail(eventTarget.target.value)}
                      required
                    />
                  </label>
                </div>
                <label className="choice-line">
                  <input
                    type="checkbox"
                    checked={avecAnonymous}
                    onChange={(eventTarget) => setAvecAnonymous(eventTarget.target.checked)}
                  />
                  <span>Avec anonym i deltagarlistan</span>
                </label>
                {event.sign_up_fields
                  .filter((field) => !field.hide_for_avec)
                  .map((field) => renderDynamicField(field, avecDynamicValues, setAvecDynamicValues, "avec-"))}
              </div>
            ) : null}
          </fieldset>
        ) : null}

        {event.captcha ? (
          <label className="form-field">
            <span>Turnstile token</span>
            <input
              value={captchaToken}
              onChange={(eventTarget) => setCaptchaToken(eventTarget.target.value)}
              placeholder="Krävs när captcha är aktiverad"
              required
            />
          </label>
        ) : null}

        <button className="button" type="submit" disabled={isSubmittingSignup}>
          {isSubmittingSignup ? "Anmäler..." : "Anmäl"}
        </button>
      </form>
      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
      {statusMessage ? <p className="form-success">{statusMessage}</p> : null}
      {signupResult ? (
        <section className="content event-detail-content">
          <h3>Anmälningssammanfattning</h3>
          <p className="meta">E-post: {signupResult.attendee_email}</p>
          <p className="meta">{billingStatusLabel(signupResult.billing)}</p>
          {signupResult.billing.invoice ? (
            <ul className="list">
              <li>Fakturanummer: {signupResult.billing.invoice.invoice_number}</li>
              <li>Referensnummer: {signupResult.billing.invoice.reference_number}</li>
              <li>
                Belopp: {signupResult.billing.invoice.amount} {signupResult.billing.invoice.currency}
              </li>
              <li>Förfallodatum: {signupResult.billing.invoice.due_date}</li>
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
