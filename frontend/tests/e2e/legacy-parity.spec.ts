import { expect, test, type APIRequestContext } from "@playwright/test";

const parityChecksEnabled = process.env.PLAYWRIGHT_ENABLE_PARITY === "1";

type ModuleCapability = {
  enabled?: boolean;
};

type SiteMetaResponse = {
  data?: {
    project_name?: string;
    default_landing_path?: string;
    association_theme?: {
      brand?: string;
    };
    module_capabilities?: Record<string, ModuleCapability>;
  };
};

async function getSiteMetaData(request: APIRequestContext) {
  const response = await request.get("/api/v1/meta/site");
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as SiteMetaResponse;
  return payload.data ?? {};
}

function isModuleEnabled(meta: SiteMetaResponse["data"], moduleName: string) {
  return meta?.module_capabilities?.[moduleName]?.enabled === true;
}

test.describe("legacy template parity", () => {
  test.skip(
    !parityChecksEnabled,
    "Legacy parity checks are disabled. Set PLAYWRIGHT_ENABLE_PARITY=1 to run this suite.",
  );

  test("header and footer keep legacy shell classes", async ({ page }) => {
    await page.goto("/");

    await expect(page.locator("header.legacy-site-header .legacy-navbar")).toBeVisible();
    await expect(page.locator("button.legacy-nav-toggler")).toHaveAttribute(
      "data-bs-target",
      "#legacyNavOffcanvas",
    );
    await expect(page.locator("footer.legacy-site-footer")).toBeVisible();
  });

  test("home route keeps legacy hero and module containers", async ({ page, request }) => {
    const meta = await getSiteMetaData(request);
    const defaultLandingPath = meta.default_landing_path ?? "/";
    test.skip(defaultLandingPath !== "/", "Default landing path is not home route.");
    const projectName = (meta.project_name ?? "").toLowerCase();
    const brand = (meta.association_theme?.brand ?? projectName).toLowerCase();
    const isBiocum = brand === "biocum";

    await page.goto("/");

    if (isBiocum) {
      await expect(page.locator(".home-hero-legacy.header.wave .text")).toBeVisible();
    } else {
      await expect(page.locator(".home-hero-legacy .hero-text-box")).toBeVisible();
    }
    const animatedLogoCount = await page
      .locator(".home-hero-logo-inline--animated, .home-hero-logo--animated")
      .count();
    expect(animatedLogoCount).toBeGreaterThan(0);

    await expect(page.locator("#news.news-events")).toBeVisible();

    if (isModuleEnabled(meta, "news")) {
      await expect(page.locator(".feed-container")).toBeVisible();
    }

    if (isModuleEnabled(meta, "events")) {
      await expect(page.locator(".events-container")).toBeVisible();
      const eventCardCount = await page.locator(".events-container .event-card").count();
      const emptyStateCount = await page.getByText("Inga aktiva evenemang hittades...").count();
      expect(eventCardCount > 0 || emptyStateCount > 0).toBeTruthy();
    }
  });

  test("events index keeps legacy card and past-events structure", async ({ page, request }) => {
    const meta = await getSiteMetaData(request);
    test.skip(!isModuleEnabled(meta, "events"), "Events module is disabled.");

    await page.goto("/events");

    await expect(page.locator(".events-index-page .container-size")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Kommande handelser" })).toBeVisible();

    const upcomingCardCount = await page.locator(".events-index-page .event-card").count();
    const emptyUpcomingState = await page.getByText("Inga aktiva handelser").count();
    expect(upcomingCardCount > 0 || emptyUpcomingState > 0).toBeTruthy();

    await expect(page.getByRole("heading", { name: "Tidigare handelser" })).toBeVisible();
  });
});
