import { expect, test } from "@playwright/test";

type SiteMetaResponse = {
  data?: {
    project_name?: string;
    association_theme?: {
      brand?: string;
    };
  };
};

type HostExpectation = {
  host: string;
  expectedProject: string;
};

const HOST_EXPECTATIONS: HostExpectation[] = [
  { host: "date.lvh.me:8080", expectedProject: "date" },
  { host: "kk.lvh.me:8080", expectedProject: "kk" },
  { host: "on.lvh.me:8080", expectedProject: "on" },
];

function normalizeBrand(input: string | undefined): string {
  return (input ?? "").toLowerCase().replace(/[^a-z0-9-]/g, "");
}

test.describe("multi-host frontend smoke", () => {
  test.skip(process.env.PLAYWRIGHT_MULTI_HOST !== "1", "Set PLAYWRIGHT_MULTI_HOST=1 to run host matrix smoke.");

  for (const item of HOST_EXPECTATIONS) {
    test(`host ${item.host} resolves project + theme correctly`, async ({ page, request }) => {
      const origin = `http://${item.host}`;

      const apiContext = await request.newContext({
        baseURL: origin,
      });
      const metaResponse = await apiContext.get("/api/v1/meta/site");
      expect(metaResponse.ok()).toBeTruthy();
      const meta = (await metaResponse.json()) as SiteMetaResponse;

      expect(meta.data?.project_name).toBe(item.expectedProject);
      const expectedBrand = normalizeBrand(meta.data?.association_theme?.brand ?? meta.data?.project_name);

      await page.goto(origin);
      await page.waitForLoadState("domcontentloaded");

      const renderedBrand = await page.locator("body").getAttribute("data-association");
      expect(normalizeBrand(renderedBrand ?? "")).toBe(expectedBrand);
    });
  }
});
