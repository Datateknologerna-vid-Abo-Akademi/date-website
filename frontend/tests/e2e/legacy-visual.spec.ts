import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const visualChecksEnabled = process.env.PLAYWRIGHT_ENABLE_VISUAL === "1";

type SiteMetaResponse = {
  data?: {
    association_theme?: {
      brand?: string;
    };
    project_name?: string;
    module_capabilities?: Record<string, { enabled?: boolean }>;
  };
};

type EventsListResponse = {
  data?: Array<{
    slug: string;
  }>;
};

type EventDetailResponse = {
  data?: {
    template_variant?: string;
  };
};

const REQUIRED_VARIANTS = [
  "default",
  "arsfest",
  "baal",
  "kk100",
  "tomtejakt",
  "wappmiddag",
] as const;

type RequiredVariant = (typeof REQUIRED_VARIANTS)[number];

async function getSiteMeta(request: APIRequestContext) {
  const response = await request.get("/api/v1/meta/site");
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as SiteMetaResponse;
}

function snapshotSuffix(meta: SiteMetaResponse) {
  const brand = meta.data?.association_theme?.brand ?? meta.data?.project_name ?? "default";
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
    `,
  });
}

async function getVariantSlugs(request: APIRequestContext) {
  const response = await request.get("/api/v1/events?include_past=true");
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as EventsListResponse;
  const events = payload.data ?? [];
  const result: Partial<Record<RequiredVariant, string>> = {};

  for (const event of events) {
    const detailResponse = await request.get(`/api/v1/events/${event.slug}`);
    if (!detailResponse.ok()) continue;
    const detailPayload = (await detailResponse.json()) as EventDetailResponse;
    const variant = (detailPayload.data?.template_variant ?? "default") as RequiredVariant;
    if (!REQUIRED_VARIANTS.includes(variant)) continue;
    if (!result[variant]) {
      result[variant] = event.slug;
    }
    const allResolved = REQUIRED_VARIANTS.every((requiredVariant) => Boolean(result[requiredVariant]));
    if (allResolved) break;
  }

  return result;
}

test.describe("legacy route visual regression", () => {
  test.skip(
    !visualChecksEnabled,
    "Visual checks are disabled. Set PLAYWRIGHT_ENABLE_VISUAL=1 to run this suite.",
  );

  test("members login form matches approved baseline", async ({ page, request }) => {
    const meta = await getSiteMeta(request);

    await page.goto("/members/login", { waitUntil: "networkidle" });
    await stabilizeVisuals(page);

    const loginForm = page.getByTestId("auth-shell-card").first();
    await expect(loginForm).toBeVisible();
    await expect(loginForm).toHaveScreenshot(`members-login-${snapshotSuffix(meta)}.png`, {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      maxDiffPixelRatio: 0.03,
    });
  });

  test("events index matches approved baseline", async ({ page, request }) => {
    const meta = await getSiteMeta(request);
    const eventsEnabled = meta.data?.module_capabilities?.events?.enabled === true;
    test.skip(!eventsEnabled, "Events module is disabled.");

    await page.goto("/events", { waitUntil: "networkidle" });
    await stabilizeVisuals(page);

    const eventsIndex = page.locator(".events-index-page .container-size").first();
    await expect(eventsIndex).toBeVisible();
    await expect(eventsIndex).toHaveScreenshot(`events-index-${snapshotSuffix(meta)}.png`, {
      animations: "disabled",
      caret: "hide",
      scale: "css",
      maxDiffPixelRatio: 0.03,
    });
  });

  test("event detail variants match approved baselines", async ({ page, request }) => {
    const meta = await getSiteMeta(request);
    const eventsEnabled = meta.data?.module_capabilities?.events?.enabled === true;
    test.skip(!eventsEnabled, "Events module is disabled.");

    const variantSlugs = await getVariantSlugs(request);
    const missingVariants = REQUIRED_VARIANTS.filter((variant) => !variantSlugs[variant]);
    test.skip(
      missingVariants.length > 0,
      `Missing seeded events for variants: ${missingVariants.join(", ")}. Seed demo data first (python /code/manage.py seed_visual_demo).`,
    );

    for (const variant of REQUIRED_VARIANTS) {
      const slug = variantSlugs[variant];
      if (!slug) continue;

      await page.goto(`/events/${slug}`, { waitUntil: "networkidle" });
      await stabilizeVisuals(page);

      const detailContainer = page.locator(".event-detail-page .event-detail-container").first();
      await expect(detailContainer).toBeVisible();
      await expect(detailContainer).toHaveScreenshot(
        `events-detail-${variant}-${snapshotSuffix(meta)}.png`,
        {
          animations: "disabled",
          caret: "hide",
          scale: "css",
          maxDiffPixelRatio: 0.05,
        },
      );
    }
  });
});
