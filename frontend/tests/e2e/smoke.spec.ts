import { expect, test } from "@playwright/test";

type ModuleCapability = {
  enabled?: boolean;
};

type SiteMetaResponse = {
  data?: {
    project_name?: string;
    default_landing_path?: string;
    module_capabilities?: Record<string, ModuleCapability>;
  };
};

type SessionPayload = {
  data?: {
    is_authenticated?: boolean;
    username?: string;
  };
};

function extractCookieValue(setCookieHeader: string, cookieName: string): string {
  const pattern = new RegExp(`${cookieName}=([^;]+)`);
  const match = setCookieHeader.match(pattern);
  return match?.[1] ?? "";
}

test.describe("decoupled frontend smoke checks", () => {
  test("core routes respond and meta contract is available", async ({ request }) => {
    const metaResponse = await request.get("/api/v1/meta/site");
    expect(metaResponse.ok()).toBeTruthy();

    const metaPayload = (await metaResponse.json()) as SiteMetaResponse;
    const expectedProjectName = process.env.PLAYWRIGHT_EXPECT_PROJECT_NAME;
    if (expectedProjectName) {
      expect(metaPayload.data?.project_name).toBe(expectedProjectName);
    }
    const landingPath = metaPayload.data?.default_landing_path ?? "/";
    expect(landingPath.startsWith("/")).toBeTruthy();

    const rootResponse = await request.get("/");
    expect(rootResponse.status()).toBeLessThan(500);

    const landingResponse = await request.get(landingPath);
    expect(landingResponse.status()).toBeLessThan(500);

    const eventsResponse = await request.get("/events");
    expect(eventsResponse.status()).toBeLessThan(500);
  });

  test("module guard behavior matches lucia capability", async ({ request }) => {
    const metaResponse = await request.get("/api/v1/meta/site");
    expect(metaResponse.ok()).toBeTruthy();

    const metaPayload = (await metaResponse.json()) as SiteMetaResponse;
    const luciaEnabled = metaPayload.data?.module_capabilities?.lucia?.enabled === true;

    const luciaResponse = await request.get("/lucia");
    if (luciaEnabled) {
      expect(luciaResponse.status()).toBeLessThan(500);
      return;
    }

    expect(luciaResponse.status()).toBe(404);
  });

  test("anonymous session endpoint sets csrf cookie", async ({ request }) => {
    const sessionResponse = await request.get("/api/v1/auth/session");
    expect(sessionResponse.ok()).toBeTruthy();

    const payload = (await sessionResponse.json()) as SessionPayload;
    expect(payload.data?.is_authenticated).toBe(false);

    const setCookieHeader = sessionResponse.headers()["set-cookie"] ?? "";
    expect(setCookieHeader.toLowerCase()).toContain("csrftoken=");
  });

  test("login updates session state and logout clears it", async ({ request }) => {
    const username = process.env.PLAYWRIGHT_SMOKE_USERNAME;
    const password = process.env.PLAYWRIGHT_SMOKE_PASSWORD;
    test.skip(!username || !password, "Playwright smoke credentials are required.");

    const csrfBootstrapResponse = await request.get("/api/v1/auth/session");
    expect(csrfBootstrapResponse.ok()).toBeTruthy();
    const csrfToken = extractCookieValue(csrfBootstrapResponse.headers()["set-cookie"] ?? "", "csrftoken");
    expect(csrfToken).not.toBe("");

    const loginResponse = await request.post("/api/v1/auth/login", {
      headers: {
        "X-CSRFToken": csrfToken,
        Referer: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:8080",
      },
      data: { username, password },
    });
    expect(loginResponse.ok()).toBeTruthy();

    const sessionAfterLogin = await request.get("/api/v1/auth/session");
    expect(sessionAfterLogin.ok()).toBeTruthy();
    const sessionPayload = (await sessionAfterLogin.json()) as SessionPayload;
    expect(sessionPayload.data?.is_authenticated).toBe(true);
    expect(sessionPayload.data?.username).toBe(username);
    const refreshedCsrfToken =
      extractCookieValue(sessionAfterLogin.headers()["set-cookie"] ?? "", "csrftoken") || csrfToken;

    const logoutResponse = await request.post("/api/v1/auth/logout", {
      headers: {
        "X-CSRFToken": refreshedCsrfToken,
        Referer: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:8080",
      },
    });
    expect(logoutResponse.ok()).toBeTruthy();

    const sessionAfterLogout = await request.get("/api/v1/auth/session");
    expect(sessionAfterLogout.ok()).toBeTruthy();
    const sessionAfterLogoutPayload = (await sessionAfterLogout.json()) as SessionPayload;
    expect(sessionAfterLogoutPayload.data?.is_authenticated).toBe(false);
  });

  test("members login page supports browser sign-in and sign-out", async ({ page }) => {
    const username = process.env.PLAYWRIGHT_SMOKE_USERNAME ?? "";
    const password = process.env.PLAYWRIGHT_SMOKE_PASSWORD ?? "";
    test.skip(!username || !password, "Playwright smoke credentials are required.");

    await page.goto("/members/login");
    await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
    await page.getByLabel("Användarnamn").fill(username);
    await page.getByLabel("Lösenord").fill(password);
    await page.getByRole("button", { name: /login/i }).click();

    await expect(page).toHaveURL(/\/members\/profile$/);
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/members\/login$/);
  });

  test("event detail page supports signup flow for open event", async ({ page }) => {
    const eventSlug = process.env.PLAYWRIGHT_SMOKE_EVENT_SLUG ?? "ci-smoke-event";
    const uniqueEmail = `playwright-smoke-${Date.now()}@example.com`;

    await page.goto(`/events/${eventSlug}`);
    await expect(page.getByRole("heading", { name: "CI Smoke Event" })).toBeVisible();
    await page.getByLabel("Namn").fill("Playwright Smoke");
    await page.getByLabel("E-post").fill(uniqueEmail);
    const signupResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes(`/api/v1/events/${eventSlug}/signup`) &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Anmäl" }).click();
    const signupResponse = await signupResponsePromise;
    expect(signupResponse.ok()).toBeTruthy();

    await expect(page.getByText("Anmälning registrerad.")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Anmälningssammanfattning" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(`E-post: ${uniqueEmail}`)).toBeVisible();
  });
});
