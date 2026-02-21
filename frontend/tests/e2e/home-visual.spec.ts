import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const visualChecksEnabled = process.env.PLAYWRIGHT_ENABLE_VISUAL === "1";

type SiteMetaResponse = {
  data?: {
    default_landing_path?: string;
    project_name?: string;
    association_theme?: {
      brand?: string;
    };
    module_capabilities?: Record<string, { enabled?: boolean }>;
  };
};

async function getSiteMeta(request: APIRequestContext) {
  const response = await request.get("/api/v1/meta/site");
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as SiteMetaResponse;
}

function snapshotSuffix(meta: SiteMetaResponse) {
  const brand =
    meta.data?.association_theme?.brand ??
    meta.data?.project_name ??
    "default";
  return brand.toLowerCase().replace(/[^a-z0-9_-]/g, "-");
}

async function stabilizeVisuals(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
      }
      .events-container .event-card .card-title,
      .events-container .event-card .list-inline-item,
      .events-container .event-card .text-color,
      .events-container .event-card .badge {
        color: #5f5f5f !important;
        text-shadow: none !important;
      }
      .events-container .event-card .badge {
        background-color: #9c9c9c !important;
      }
    `,
  });
}

test.describe("homepage visual regression", () => {
  test.skip(
    !visualChecksEnabled,
    "Visual checks are disabled. Set PLAYWRIGHT_ENABLE_VISUAL=1 to run this suite.",
  );

  test("hero shell matches approved baseline", async ({ page, request }) => {
    const meta = await getSiteMeta(request);
    const defaultLandingPath = meta.data?.default_landing_path ?? "/";
    test.skip(defaultLandingPath !== "/", "Default landing path is not home route.");

    await page.goto("/", { waitUntil: "networkidle" });
    await stabilizeVisuals(page);

    const hero = page.locator(".header").first();
    await expect(hero).toBeVisible();
    await expect(hero).toHaveScreenshot(`home-hero-${snapshotSuffix(meta)}.png`, {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      maxDiffPixelRatio: 0.03,
    });
  });

  test("events cards under calendar match approved baseline", async ({ page, request }) => {
    const meta = await getSiteMeta(request);
    const defaultLandingPath = meta.data?.default_landing_path ?? "/";
    test.skip(defaultLandingPath !== "/", "Default landing path is not home route.");

    const eventsEnabled = meta.data?.module_capabilities?.events?.enabled === true;
    test.skip(!eventsEnabled, "Events module is disabled.");

    await page.goto("/", { waitUntil: "networkidle" });
    await stabilizeVisuals(page);

    const eventsSection = page.locator(".events-container .events").first();
    await expect(eventsSection).toBeVisible();
    await expect(eventsSection).toHaveScreenshot(`home-events-cards-${snapshotSuffix(meta)}.png`, {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      maxDiffPixelRatio: 0.03,
    });
  });
});
