import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sourceExtensions = new Set([".css", ".js", ".jsx", ".scss", ".ts", ".tsx"]);
const excludedDirectories = new Set([".next", "node_modules", "out", "playwright-report", "test-results"]);

const forbiddenDependencies = [
  { label: "next/font/google", pattern: /next\/font\/google/i },
  { label: "Google Fonts stylesheet", pattern: /fonts\.googleapis\.com/i },
  { label: "Google Fonts asset", pattern: /fonts\.gstatic\.com/i },
  {
    label: "remote font asset",
    pattern: /url\(\s*["']?https?:\/\/[^)]*\.(?:woff2?|ttf|otf)(?:[?#][^)]*)?["']?\s*\)/i,
  },
];

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isDirectory()) {
      return excludedDirectories.has(entry.name) ? [] : sourceFiles(join(directory, entry.name));
    }
    if (!sourceExtensions.has(extname(entry.name)) || /\.(?:spec|test)\.[^.]+$/.test(entry.name)) {
      return [];
    }
    return [join(directory, entry.name)];
  });
}

test("frontend typography has no remote build-time dependency", () => {
  const violations = sourceFiles(frontendRoot).flatMap((path) => {
    const source = readFileSync(path, "utf8");
    return forbiddenDependencies
      .filter(({ pattern }) => pattern.test(source))
      .map(({ label }) => `${relative(frontendRoot, path)}: ${label}`);
  });

  assert.deepEqual(violations, []);
});
