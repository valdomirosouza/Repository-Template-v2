// ESLint 9 flat config (W14-T10): Next 16 removed `next lint`; eslint-config-next 16 ships flat presets.
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores(["src/lib/api/", ".next/", "coverage/", "playwright-report/", "test-results/"]),
]);
