"use client";

import { useState } from "react";

const COOKIE_STORAGE_KEY = "cookiesAccepted";

export function CookieBanner() {
  const [visible, setVisible] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem(COOKIE_STORAGE_KEY) === null;
  });

  function onChoice(value: "true" | "false") {
    window.localStorage.setItem(COOKIE_STORAGE_KEY, value);
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div id="cookie-banner" role="dialog" aria-live="polite" aria-label="Cookie consent">
      <div className="cookie-banner-content">
        <p className="cookie-banner-text">
          Vi använder cookies för att förbättra din upplevelse på vår webbplats. Genom att fortsätta använda webbplatsen godkänner du vår användning av cookies.
        </p>
        <div className="cookie-banner-buttons">
          <button id="accept-cookies" className="cookie-banner-button" type="button" onClick={() => onChoice("true")}>
            Godkänn
          </button>
          <button id="decline-cookies" className="cookie-banner-button" type="button" onClick={() => onChoice("false")}>
            Avböj
          </button>
        </div>
      </div>
    </div>
  );
}
