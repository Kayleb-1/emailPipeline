import { describe, expect, test } from "bun:test";
import {
  MARK_END, MARK_START, facetCounts, ftsQuery, getEmail, listEmails, parseFilters, type Filters,
} from "../server/query.ts";
import { SAMPLE, fixtureDb } from "./fixture-db.ts";

const db = fixtureDb(SAMPLE);
const f = (qs: string): Filters => parseFilters(new URLSearchParams(qs));
const ids = (qs: string) => listEmails(db, f(qs)).items.map((i) => i.source_file);

describe("parseFilters", () => {
  test("repeated and comma-separated values, deduplicated", () => {
    const p = f("asset=FX&asset=Equity,FX&bank=+Bank A+&sort=old&q=  semis ");
    expect(p.asset).toEqual(["FX", "Equity"]);
    expect(p.bank).toEqual(["Bank A"]);
    expect(p.sort).toBe("old");
    expect(p.q).toBe("semis");
  });
  test("defaults", () => {
    const p = f("");
    expect(p.sort).toBe("new");
    expect(p.asset).toEqual([]);
  });
});

describe("ftsQuery", () => {
  test("words become quoted prefix terms joined by AND", () => {
    expect(ftsQuery("Company alpha")).toBe('"Company"* AND "alpha"*');
  });
  test("FTS syntax in user text is neutralised", () => {
    expect(ftsQuery('a" OR body:* NEAR(')).toBe('"a"* AND "OR"* AND "body"* AND "NEAR"*');
    expect(ftsQuery("  ** ")).toBeNull();
  });
});

describe("listEmails", () => {
  test("no filters: everything, newest first, no date last", () => {
    const res = listEmails(db, f(""));
    expect(res.total).toBe(4);
    expect(res.items.map((i) => i.source_file)).toEqual(["002", "001", "003", "004"]);
  });
  test("oldest first keeps no date last", () => {
    expect(ids("sort=old")).toEqual(["003", "001", "002", "004"]);
  });
  test("items carry the ten fields", () => {
    const item = listEmails(db, f("")).items[1];
    expect(item.folder_name).toBe("Semis: raising estimates");
    expect(item.pdf_attachment).toEqual(["semis.pdf"]);
  });
  test("asset: OR within the facet, parent catches its sub-tags", () => {
    expect(ids("asset=Equity,Market Wrap")).toEqual(["002", "001"]);
    expect(ids("asset=FX")).toEqual(["003", "004"]);
    expect(ids("asset=JPY")).toEqual(["003"]);
  });
  test("bank, industry, company, wrap", () => {
    expect(ids("bank=Bank A")).toEqual(["001", "003"]);
    expect(ids("industry=TECHNOLOGY > Semiconductors")).toEqual(["001"]);
    expect(ids("company=Company Alpha")).toEqual(["001"]);
    expect(ids("wrap=YES")).toEqual(["002"]);
  });
  test("month filter, including no date", () => {
    expect(ids("month=2026-04")).toEqual(["002", "001"]);
    expect(ids("month=none")).toEqual(["004"]);
    expect(ids("month=2026-03,none")).toEqual(["003", "004"]);
  });
  test("AND across facets", () => {
    expect(ids("asset=FX&bank=Bank A")).toEqual(["003"]);
    expect(ids("asset=FX&bank=Bank B")).toEqual([]);
  });
  test("full-text search reaches body and PDF text, with prefixes and diacritics", () => {
    expect(ids("q=zygomorph")).toEqual(["001"]);
    expect(ids("q=quokka")).toEqual(["001"]);
    expect(ids("q=cafe")).toEqual(["002"]);
    expect(ids("q=company alpha")).toEqual(["001"]);
  });
  test("search combines with filters", () => {
    expect(ids("q=steepening&asset=FX")).toEqual(["004"]);
    expect(ids("q=steepening&bank=Bank A")).toEqual([]);
  });
  test("snippets mark the hit with control characters", () => {
    const [item] = listEmails(db, f("q=quokka")).items;
    expect(item.snippet).toContain(`${MARK_START}Quokka${MARK_END}`);
    expect(listEmails(db, f("")).items[0].snippet).toBeNull();
  });
  test("injection attempts are just values", () => {
    expect(ids("bank=' OR 1=1 --")).toEqual([]);
    expect(ids("q=\") OR 1=1 --")).toEqual([]);
  });
});

describe("facetCounts", () => {
  test("unfiltered counts", () => {
    const c = facetCounts(db, f(""));
    expect(c.asset).toMatchObject({ Equity: 1, FX: 2, USD: 2, JPY: 1, "Market Wrap": 1 });
    expect(c.bank).toEqual({ "Bank A": 2, "Bank B": 1, "Bank C": 1 });
    expect(c.month).toEqual({ "2026-04": 2, "2026-03": 1, none: 1 });
    expect(c.wrap).toEqual({ YES: 1, NO: 3 });
  });
  test("a facet ignores its own selection but applies the others", () => {
    const c = facetCounts(db, f("bank=Bank A&asset=FX"));
    expect(c.bank).toEqual({ "Bank A": 1, "Bank B": 0, "Bank C": 1 });
    expect(c.asset).toMatchObject({ Equity: 1, FX: 1, "Market Wrap": 0 });
    expect(c.month).toEqual({ "2026-04": 0, "2026-03": 1, none: 0 });
  });
  test("search narrows every facet", () => {
    const c = facetCounts(db, f("q=yen"));
    expect(c.bank).toEqual({ "Bank A": 1, "Bank B": 0, "Bank C": 0 });
  });
});

test("getEmail returns the record or null", () => {
  expect(getEmail(db, "003")?.asset_tags).toEqual(["FX", "USD", "JPY"]);
  expect(getEmail(db, "nope")).toBeNull();
});
