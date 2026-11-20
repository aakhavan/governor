import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { fold } from "./fold";
import type { RunView } from "./types";

interface FoldCase {
  name: string;
  events: Record<string, unknown>[];
  expected: RunView;
}

const fixture = resolve(dirname(fileURLToPath(import.meta.url)), "../../../../tests/fixtures/console/fold_cases.json");
const cases = JSON.parse(readFileSync(fixture, "utf8")) as FoldCase[];

describe("fold parity", () => {
  it.each(cases.map((item) => [item.name, item] as const))("%s", (_name, item) => {
    expect(fold(item.events)).toEqual(item.expected);
  });
});
