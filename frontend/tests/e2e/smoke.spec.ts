import { expect, test } from "@playwright/test";

type ModuleCapability = {
  enabled?: boolean;
};

type SiteMetaResponse = {
  data?: {
    default_landing_path?: string;
    module_capabilities?: Record<string, ModuleCapability>;
  };
};

test.describe("decoupled frontend smoke checks", () => {
  test("core routes respond and meta contract is available", async ({ request }) => {
    const metaResponse = await request.get("/api/v1/meta/site");
    expect(metaResponse.ok()).toBeTruthy();

    const metaPayload = (await metaResponse.json()) as SiteMetaResponse;
    const landingPath = metaPayload.data?.default_landing_path ?? "/";
    expect(landingPath.startsWith("/")).toBeTruthy();

    const rootResponse = await request.get("/");
    expect(rootResponse.status()).toBeLessThan(500);

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
});
