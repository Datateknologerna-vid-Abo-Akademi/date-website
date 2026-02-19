"use client";

import { useEffect, useMemo, useRef } from "react";

type CalendarEvent = {
  link: string;
  modifier: string;
  eventFullDate: string;
  eventTitle: string;
};

interface HomeCalendarProps {
  events: Record<string, CalendarEvent>;
}

interface VanillaCalendarInstance {
  init: () => void;
}

type VanillaCalendarCtor = new (
  element: HTMLElement,
  options: {
    actions?: {
      clickDay?: (_event: unknown, date: string[]) => void;
    };
    settings?: {
      visibility?: {
        weekend?: boolean;
      };
      selected?: {
        month?: number;
        year?: number;
      };
    };
    popups?: Record<
      string,
      {
        modifier?: string;
        html?: string;
      }
    >;
  },
) => VanillaCalendarInstance;

declare global {
  interface Window {
    VanillaCalendar?: VanillaCalendarCtor;
  }
}

function isValidInternalUrl(url: string) {
  if (!url) return false;
  const trimmed = url.trim();
  if (!trimmed || trimmed.startsWith("//")) return false;
  const lower = trimmed.toLowerCase();
  if (
    lower.startsWith("javascript:") ||
    lower.startsWith("data:") ||
    lower.startsWith("vbscript:")
  ) {
    return false;
  }
  if (trimmed.startsWith("/")) return true;
  try {
    const parsed = new URL(trimmed, window.location.origin);
    return parsed.origin === window.location.origin;
  } catch {
    return false;
  }
}

function normalizeInternalUrl(url: string) {
  if (!isValidInternalUrl(url)) return "#";
  try {
    return new URL(url, window.location.origin).href;
  } catch {
    return "#";
  }
}

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`) as HTMLScriptElement | null;
    if (existing) {
      if (existing.dataset.loaded === "true") {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Failed to load calendar script")), {
        once: true,
      });
      return;
    }

    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.defer = true;
    script.addEventListener(
      "load",
      () => {
        script.dataset.loaded = "true";
        resolve();
      },
      { once: true },
    );
    script.addEventListener("error", () => reject(new Error("Failed to load calendar script")), {
      once: true,
    });
    document.body.appendChild(script);
  });
}

function ensureCalendarStylesheet() {
  const href = "/static/date/css/vanilla-calendar.min.css";
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

export function HomeCalendar({ events }: HomeCalendarProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const popups = useMemo(() => {
    const nextPopups: Record<string, { modifier: string; html: string }> = {};

    Object.entries(events).forEach(([dateKey, value]) => {
      const parsedDate = new Date(value.eventFullDate);
      const hours = Number.isNaN(parsedDate.getTime())
        ? "00"
        : String(parsedDate.getHours()).padStart(2, "0");
      const minutes = Number.isNaN(parsedDate.getTime())
        ? "00"
        : String(parsedDate.getMinutes()).padStart(2, "0");
      const href = normalizeInternalUrl(value.link);
      const title = value.eventTitle.replace(/</g, "&lt;").replace(/>/g, "&gt;");
      nextPopups[dateKey] = {
        modifier: value.modifier || "calendar-eventday",
        html: `<a class="calendar-eventday-popup" href="${href}">${hours}:${minutes}<br>${title}</a>`,
      };
    });

    return nextPopups;
  }, [events]);

  useEffect(() => {
    let isMounted = true;

    async function initCalendar() {
      if (!ref.current) return;
      ensureCalendarStylesheet();
      await loadScript("/static/date/js/vanilla-calendar.min.js");
      if (!isMounted || !ref.current || !window.VanillaCalendar) return;

      const calendar = new window.VanillaCalendar(ref.current, {
        actions: {
          clickDay(_event, date) {
            const selected = Array.isArray(date) ? date[0] : "";
            const item = selected ? events[selected] : undefined;
            if (!item || !isValidInternalUrl(item.link)) return;
            const href = normalizeInternalUrl(item.link);
            if (href !== "#") {
              window.location.href = href;
            }
          },
        },
        settings: {
          visibility: { weekend: false },
          selected: {
            month: new Date().getMonth(),
            year: new Date().getFullYear(),
          },
        },
        popups,
      });
      calendar.init();
    }

    initCalendar().catch(() => undefined);
    return () => {
      isMounted = false;
    };
  }, [events, popups]);

  return <div className="calendar" ref={ref} />;
}
