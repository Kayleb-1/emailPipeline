// The brief's asset taxonomy with the v5 design's icons and per-class colours.

export const TAXONOMY: [primary: string, subs: string[], icon: string][] = [
  ["Macro", ["Developed Markets", "Emerging Markets"], "public"],
  ["Fixed Income", ["Credit Strategy", "Rates Strategy", "Securitisation"], "account_balance"],
  ["Equity", ["Company Research", "Portfolio Strategy", "Thematic Investing"], "candlestick_chart"],
  ["Commodities", ["Energy", "Metals", "Agriculture"], "oil_barrel"],
  ["FX", ["USD", "EUR", "JPY", "GBP", "CHF", "Other"], "currency_exchange"],
  ["Thematics", [], "lightbulb"],
  ["Market Wrap", [], "newspaper"],
];

export const PARENT: Record<string, string> = Object.fromEntries(
  TAXONOMY.flatMap(([p, subs]) => subs.map((s) => [s, p])),
);
export const ICON: Record<string, string> = Object.fromEntries(TAXONOMY.map(([p, , i]) => [p, i]));

export type ClassColour = { bg: string; fg: string; accent: string; onAccent: string };

const COLOURS: Record<string, [string, string, string, string]> = {
  Macro: ["#4f378b", "#eaddff", "#d0bcff", "#381e72"],
  "Fixed Income": ["#0f5132", "#b7f1cf", "#9cd5b3", "#00391f"],
  Equity: ["#004a77", "#cfe5ff", "#98cbff", "#003354"],
  Commodities: ["#5b4300", "#ffdf9e", "#f3bf48", "#402d00"],
  FX: ["#004f58", "#9eefff", "#82d3e2", "#00363d"],
  Thematics: ["#6f2f55", "#ffd8ea", "#ffafd6", "#55193e"],
  "Market Wrap": ["#44474e", "#e0e2ec", "#c4c6d0", "#2e3036"],
};
const FALLBACK: ClassColour = { bg: "rgba(240,40,127,.16)", fg: "#FF8FC2", accent: "#F0287F", onAccent: "#FFFFFF" };

/** Colours for a tag: a sub-tag takes its primary class's colours. */
export function classColour(tag: string): ClassColour {
  const v = COLOURS[PARENT[tag] ?? tag];
  return v ? { bg: v[0], fg: v[1], accent: v[2], onAccent: v[3] } : FALLBACK;
}

export const iconFor = (tag: string) => ICON[PARENT[tag] ?? tag] ?? "label";
