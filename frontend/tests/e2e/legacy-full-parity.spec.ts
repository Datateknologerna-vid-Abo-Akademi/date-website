import { expect, test } from "@playwright/test";

import {
  availableRouteChunks,
  assertLegacyTemplateVariantParity,
  buildRouteManifest,
  ensureAuthenticatedContext,
  filterManifestRoutes,
  readManifestOptions,
  snapshotPathForRoute,
  snapshotSuffix,
  stabilizePageForVisual,
  type AuthMode,
} from "./utils/legacy-full-parity";

function parseAuthModesFromEnv(): AuthMode[] {
  const configured = (process.env.PLAYWRIGHT_PARITY_AUTH_MODES ?? "anon,member")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  const deduped = new Set<AuthMode>();
  for (const mode of configured) {
    if (mode === "anon" || mode === "member") {
      deduped.add(mode);
    }
  }
  if (deduped.size === 0) return ["anon", "member"];
  return Array.from(deduped);
}

test.describe("legacy full-route parity", () => {
  test.describe.configure({ mode: "serial" });

  for (const authMode of parseAuthModesFromEnv()) {
    test(`matches approved legacy baseline for ${authMode}`, async ({ page, request, baseURL }, testInfo) => {
      test.setTimeout(8 * 60 * 1000);

      const options = readManifestOptions();
      options.authMode = authMode;

      if (process.env.PLAYWRIGHT_PARITY_VERIFY_TEMPLATE !== "0") {
        await assertLegacyTemplateVariantParity(request);
      }

      if (authMode === "member") {
        await ensureAuthenticatedContext(page);
      }

      const activeBaseUrl = baseURL ?? process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:8080";
      const { meta, manifest } = await buildRouteManifest(request, page, activeBaseUrl, options);
      const suffix = snapshotSuffix(meta);

      if (process.env.PLAYWRIGHT_PARITY_REQUIRE_VARIANTS !== "0") {
        expect(
          manifest.missingVariants,
          manifest.missingVariants.length === 0
            ? undefined
            : `Missing event variants in seeded dataset: ${manifest.missingVariants.join(", ")}`,
        ).toEqual([]);
      }

      await testInfo.attach(`manifest-${authMode}.json`, {
        body: Buffer.from(JSON.stringify(manifest, null, 2), "utf8"),
        contentType: "application/json",
      });

      const routes = filterManifestRoutes(manifest.routes);
      expect(
        routes.length,
        `No routes selected for parity run. Available chunks: ${availableRouteChunks().join(", ")}`,
      ).toBeGreaterThan(0);

      const failures: string[] = [];
      for (const route of routes) {
        try {
          await page.goto(route.path, { waitUntil: "networkidle", timeout: 20_000 });
          await stabilizePageForVisual(page);
          const snapshotPath = snapshotPathForRoute(route.path, authMode, suffix);
          await expect(page).toHaveScreenshot(snapshotPath, {
            fullPage: true,
            animations: "disabled",
            caret: "hide",
            scale: "css",
            maxDiffPixelRatio: 0.035,
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          failures.push(`${route.path} [${route.source}] -> ${message}`);
        }
      }

      expect(
        failures,
        failures.length === 0
          ? undefined
          : `Visual parity mismatches (${authMode}) on ${routes.length} routes:\n${failures.join("\n\n")}`,
      ).toEqual([]);
    });
  }
});
