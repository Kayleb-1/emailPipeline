<script lang="ts">
  // Filters: asset classes (expandable to sub-tags), banks and months, each with counts.
  import type { Facets } from "../lib/api.ts";
  import { activeCount, type FacetKey, type FilterState } from "../lib/filters.ts";
  import { monthLabel, sortMonths } from "../lib/format.ts";
  import { TAXONOMY, classColour } from "../lib/taxonomy.ts";
  import FilterRow from "./FilterRow.svelte";

  type Props = {
    filters: FilterState;
    facets: Facets | null;
    onToggle: (facet: FacetKey, value: string) => void;
    onClear: (facet: FacetKey) => void;
    onClearAll: () => void;
    onCollapse: () => void;
  };
  let { filters, facets, onToggle, onClear, onClearAll, onCollapse }: Props = $props();

  let expanded = $state<string[]>(["Equity"]);
  const count = (facet: "asset" | "bank" | "month", v: string) => facets?.[facet]?.[v] ?? 0;
  const maxOf = (vals: number[]) => Math.max(1, ...vals);

  const assetMax = $derived(maxOf(TAXONOMY.map(([p]) => count("asset", p))));
  const banks = $derived(Object.keys(facets?.bank ?? {}).sort((a, b) => a.localeCompare(b)));
  const bankMax = $derived(maxOf(banks.map((b) => count("bank", b))));
  const months = $derived(sortMonths(Object.keys(facets?.month ?? {})));
  const monthMax = $derived(maxOf(months.map((m) => count("month", m))));
  const nActive = $derived(activeCount(filters));

  const isOpen = (p: string, subs: string[]) =>
    subs.length > 0 && (expanded.includes(p) || subs.some((s) => filters.asset.includes(s)));
  const flip = (p: string) => (expanded = expanded.includes(p) ? expanded.filter((x) => x !== p) : [...expanded, p]);
</script>

<aside class="sidebar scroll" aria-label="Filters">
  <div class="head">
    <span class="ms accent" aria-hidden="true">tune</span>
    <h2>Filters</h2>
    {#if nActive}
      <span class="badge">{nActive}</span>
      <button type="button" class="link hv" onclick={onClearAll}>Clear all</button>
    {/if}
    <button type="button" class="icon-btn hv" class:push={!nActive} aria-label="Collapse filters" title="Collapse filters" onclick={onCollapse}>
      <span class="ms" aria-hidden="true">left_panel_close</span>
    </button>
  </div>

  {#snippet section(title: string, facet: FacetKey)}
    <div class="sec-head">
      <span class="label">{title}</span>
      {#if filters[facet].length}<button type="button" class="link hv" onclick={() => onClear(facet)}>Clear</button>{/if}
    </div>
  {/snippet}

  <section>
    {@render section("Asset class", "asset")}
    {#each TAXONOMY as [primary, subs, icon]}
      {@const k = classColour(primary)}
      {@const open = isOpen(primary, subs)}
      <FilterRow
        label={primary} n={count("asset", primary)} max={assetMax} on={filters.asset.includes(primary)}
        onToggle={() => onToggle("asset", primary)} {icon} iconColor={k.accent} fill={k.accent} barIdle={k.bg}
        subs={subs.length ? { open, onExpand: () => flip(primary) } : null}
      />
      {#if open}
        {#each subs as sub}
          <FilterRow
            label={sub} n={count("asset", sub)} max={assetMax} on={filters.asset.includes(sub)} indent
            onToggle={() => onToggle("asset", sub)} fill={k.accent} barIdle={k.bg}
          />
        {/each}
      {/if}
    {/each}
  </section>

  <section>
    {@render section("Bank", "bank")}
    {#each banks as bank}
      <FilterRow label={bank} n={count("bank", bank)} max={bankMax} on={filters.bank.includes(bank)} onToggle={() => onToggle("bank", bank)} />
    {/each}
  </section>

  <section>
    {@render section("Date", "month")}
    {#each months as m}
      <FilterRow label={monthLabel(m)} n={count("month", m)} max={monthMax} on={filters.month.includes(m)} onToggle={() => onToggle("month", m)} />
    {/each}
  </section>
</aside>

<style>
  .sidebar {
    flex: 0 0 268px; overflow-y: auto; border-right: 1px solid var(--border); padding: 10px;
    display: flex; flex-direction: column; gap: 14px; background: var(--panel);
  }
  .head { display: flex; align-items: center; gap: 6px; padding: 0 2px; }
  h2 { margin: 0; font-size: 13px; font-weight: 600; }
  .accent { font-size: 16px; color: var(--magenta); }
  .badge {
    min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; background: var(--magenta); color: #fff;
    font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; justify-content: center;
  }
  .link { height: 22px; padding: 0 7px; border: 0; border-radius: 6px; background: transparent; color: var(--pink); font-size: 11.5px; cursor: pointer; }
  .head .link { margin-left: auto; }
  .icon-btn { width: 28px; height: 28px; border: 0; border-radius: 7px; background: transparent; color: #a1a1aa; display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 0; }
  .icon-btn.push { margin-left: auto; }
  section { display: flex; flex-direction: column; gap: 2px; }
  .sec-head { display: flex; align-items: center; justify-content: space-between; padding: 0 6px 4px; min-height: 22px; }
</style>
