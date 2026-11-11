import { describe, expect, test } from "bun:test";
import {
  EMPTY, activeCount, chips, clearAll, clearFacet, fromSearchParams, toSearchParams, toggle,
} from "../src/lib/filters.ts";
import { clock, dateLong, dateShort, initials, monthLabel, snippetParts, sortMonths, splitIndustry } from "../src/lib/format.ts";
import { PARENT, classColour, iconFor } from "../src/lib/taxonomy.ts";

describe("filter state", () => {
  test("toggle adds and removes", () => {
    let s = toggle(EMPTY, "asset", "FX");
    s = toggle(s, "asset", "USD");
    expect(s.asset).toEqual(["FX", "USD"]);
    expect(toggle(s, "asset", "FX").asset).toEqual(["USD"]);
    expect(EMPTY.asset).toEqual([]);
  });
  test("clear one facet, clear all keeps the sort", () => {
    const s = { ...EMPTY, q: "oil", sort: "old" as const, asset: ["FX"], bank: ["Bank A"] };
    expect(clearFacet(s, "asset")).toMatchObject({ asset: [], bank: ["Bank A"], q: "oil" });
    expect(clearAll(s)).toEqual({ ...EMPTY, sort: "old" });
    expect(activeCount(s)).toBe(2);
  });
  test("round-trips through the URL", () => {
    const s = { ...EMPTY, q: " semis ", sort: "old" as const, asset: ["Equity", "USD"], bank: ["Bank A"], month: ["2026-04", "none"] };
    const p = toSearchParams(s, { id: "035239", tab: null });
    expect(p.toString()).toBe("q=semis&asset=Equity&asset=USD&bank=Bank+A&month=2026-04&month=none&sort=old&id=035239");
    expect(fromSearchParams(p)).toEqual({ ...s, q: "semis" });
  });
  test("defaults and junk in the URL", () => {
    expect(toSearchParams(EMPTY).toString()).toBe("");
    expect(fromSearchParams(new URLSearchParams("sort=weird&asset=&asset=FX&asset=FX"))).toEqual({ ...EMPTY, asset: ["FX"] });
  });
  test("chips label sub-tags with their class, banks and dates with the facet", () => {
    const s = { ...EMPTY, asset: ["USD", "Equity"], bank: ["Bank A"], month: ["2026-04", "none"] };
    expect(chips(s).map((c) => c.prefix + c.label)).toEqual([
      "FX › USD", "Equity", "Bank Bank A", "Date Apr 2026", "Date No date",
    ]);
  });
});

describe("format", () => {
  test("dates", () => {
    expect(monthLabel("2026-04")).toBe("Apr 2026");
    expect(monthLabel("none")).toBe("No date");
    expect(dateShort("2026-04-09")).toBe("09 Apr");
    expect(dateLong("2026-04-09")).toBe("09 Apr 2026");
    expect(dateShort(null)).toBe("No date");
    expect(sortMonths(["2026-03", "none", "2026-04", "2025-12"])).toEqual(["2026-04", "2026-03", "2025-12", "none"]);
  });
  test("initials", () => {
    expect(initials("Deutsche Bank")).toBe("DB");
    expect(initials("UBS")).toBe("UB");
    expect(initials("")).toBe("?");
  });
  test("snippet parts keep email text as plain text", () => {
    expect(snippetParts("…the \u0002ceasefire\u0003 held <b>x</b>…")).toEqual([
      { text: "…the ", hit: false }, { text: "ceasefire", hit: true }, { text: " held <b>x</b>…", hit: false },
    ]);
    expect(snippetParts(null)).toEqual([]);
  });
  test("industry split and clock", () => {
    expect(splitIndustry("TECHNOLOGY > Semiconductors")).toEqual({ sector: "TECHNOLOGY", sub: "Semiconductors" });
    expect(splitIndustry("Unknown")).toEqual({ sector: "INDUSTRY", sub: "Unknown" });
    expect(clock(null)).toBe("--:--");
    expect(clock("2026-11-11T10:05:00Z")).toMatch(/^\d\d:\d\d$/);
  });
});

describe("taxonomy", () => {
  test("sub-tags share their class colour and icon", () => {
    expect(PARENT.USD).toBe("FX");
    expect(classColour("USD")).toEqual(classColour("FX"));
    expect(iconFor("Rates Strategy")).toBe("account_balance");
    expect(classColour("Unknown thing").accent).toBe("#F0287F");
  });
});
