import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const featureFolders = ["events", "home", "members", "social"];

const fsdRules = featureFolders.map((folder) => ({
  files: [`features/${folder}/**/*.{ts,tsx,js,jsx}`],
  rules: {
    "no-restricted-imports": [
      "error",
      {
        patterns: featureFolders
          .filter((f) => f !== folder)
          .map((f) => ({
            group: [`@/features/${f}/**`, `../../${f}/**`, `../${f}/**`],
            message: `Feature-Sliced Design: Direct cross-feature import from '${f}' into '${folder}' is forbidden. Communicate via shared modules or public abstractions.`,
          })),
      },
    ],
  },
}));

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  ...fsdRules,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "playwright-report/**",
    "test-results/**",
    "*.log",
  ]),
]);

export default eslintConfig;
