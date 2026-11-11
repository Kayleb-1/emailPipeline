import { describe, expect, test } from "bun:test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Database } from "bun:sqlite";
import { arg, indexIsStale } from "../scripts/dashboard.ts";

test("arg reads --name value and --name=value", () => {
  expect(arg(["--data", "/x", "--port=4000"], "data")).toBe("/x");
  expect(arg(["--data", "/x", "--port=4000"], "port")).toBe("4000");
  expect(arg([], "data")).toBeUndefined();
});

describe("indexIsStale", () => {
  const dir = mkdtempSync(join(tmpdir(), "stale-"));
  const json = join(dir, "classified_emails.json");
  const dbPath = join(dir, "emails.db");
  writeFileSync(json, "[]");
  const sha = new Bun.CryptoHasher("sha256").update("[]").digest("hex");
  const make = (shaValue: string, dataDir: string) => {
    const db = new Database(dbPath, { create: true });
    db.exec("DROP TABLE IF EXISTS meta; CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)");
    db.query("INSERT INTO meta VALUES ('source_sha256', ?), ('data_dir', ?)").run(shaValue, dataDir);
    db.close();
  };

  test("missing index is stale", () => {
    expect(indexIsStale(join(dir, "none.db"), json, "/data")).toBe(true);
  });
  test("same JSON and data folder is fresh", () => {
    make(sha, "/data");
    expect(indexIsStale(dbPath, json, "/data")).toBe(false);
  });
  test("changed JSON or another data folder is stale", () => {
    make("old", "/data");
    expect(indexIsStale(dbPath, json, "/data")).toBe(true);
    make(sha, "/elsewhere");
    expect(indexIsStale(dbPath, json, "/data")).toBe(true);
  });
});
