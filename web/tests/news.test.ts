import { describe, expect, test } from "bun:test";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FEEDS, decodeEntities, fetchNews, mergeHeadlines, parseFeed, refresh } from "../scripts/fetch-news.ts";

const rss = readFileSync(join(import.meta.dir, "fixtures/feed-rss.xml"), "utf8");
const atom = readFileSync(join(import.meta.dir, "fixtures/feed-atom.xml"), "utf8");

describe("parseFeed", () => {
  test("RSS: CDATA, markup and entities cleaned; dates to ISO; bad items dropped", () => {
    const items = parseFeed(rss, "Wire");
    expect(items).toEqual([
      { title: "Stocks rise as yields ease", url: "https://news.example.com/a?x=1&y=2", source: "Wire", published_at: "2026-11-11T10:05:00.000Z" },
      { title: "Oil & gas shares slip — demand worries", url: "https://news.example.com/b", source: "Wire", published_at: "2026-11-11T09:40:00.000Z" },
      { title: "Undated headline", url: "https://news.example.com/c", source: "Wire", published_at: null },
    ]);
  });
  test("Atom entries", () => {
    const [first] = parseFeed(atom, "Atom");
    expect(first).toEqual({ title: "Central bank holds rates", url: "https://atom.example.com/rates?a=1&b=2", source: "Atom", published_at: "2026-11-11T10:10:00.000Z" });
  });
  test("entities", () => {
    expect(decodeEntities("A &amp; B &#x27;C&#39; &bogus;")).toBe("A & B 'C' &bogus;");
  });
});

test("mergeHeadlines dedupes by title and sorts newest first", () => {
  const merged = mergeHeadlines([parseFeed(rss, "Wire"), parseFeed(atom, "Atom")]);
  expect(merged.map((h) => h.title)).toEqual([
    "Central bank holds rates", "Stocks rise as yields ease", "Oil & gas shares slip — demand worries", "Undated headline",
  ]);
  expect(mergeHeadlines([parseFeed(rss, "Wire")], 1)).toHaveLength(1);
});

describe("fetchNews and refresh", () => {
  const ok = async (url: string) =>
    url.includes("cnbc") ? new Response(rss) : url.includes("ft.com") ? new Response(atom) : new Response("down", { status: 503 });

  test("collects what worked, reports what didn't", async () => {
    const { news, errors } = await fetchNews(FEEDS, ok, new Date("2026-11-11T10:20:00Z"));
    expect(news.updated_at).toBe("2026-11-11T10:20:00.000Z");
    expect(news.source).toBe("CNBC, FT Markets");
    expect(news.items[0].title).toBe("Central bank holds rates");
    expect(errors).toEqual(["MarketWatch: HTTP 503", "Yahoo Finance: HTTP 503"]);
  });

  test("writes the file, and keeps it when every feed fails", async () => {
    const dir = mkdtempSync(join(tmpdir(), "news-"));
    const path = join(dir, "news.json");
    expect(await refresh(path, ok)).toBe(true);
    const saved = JSON.parse(readFileSync(path, "utf8"));
    expect(saved.items.length).toBe(4);
    expect(await refresh(path, async () => new Response("", { status: 500 }))).toBe(false);
    expect(JSON.parse(readFileSync(path, "utf8"))).toEqual(saved);
    expect(existsSync(`${path}.${process.pid}.tmp`)).toBe(false);
    rmSync(dir, { recursive: true });
  });
});
