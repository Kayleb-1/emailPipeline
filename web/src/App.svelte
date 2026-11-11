<script lang="ts">
  // Dashboard shell: ticker on top, then filters | list | reader (v5 design).
  // All view state lives in the URL, so any view can be bookmarked or shared.
  import { onMount } from "svelte";
  import { fetchFacets, fetchList, type Facets, type ListItem } from "./lib/api.ts";
  import {
    activeCount, clearAll, clearFacet, fromSearchParams, toggle, toSearchParams,
    type FacetKey, type FilterState, type Sort,
  } from "./lib/filters.ts";
  import CollapsedRail from "./components/CollapsedRail.svelte";
  import FilterSidebar from "./components/FilterSidebar.svelte";
  import NoteList from "./components/NoteList.svelte";
  import Ticker from "./components/Ticker.svelte";
  import Viewer from "./components/Viewer.svelte";

  const initial = new URLSearchParams(location.search);
  let filters = $state<FilterState>(fromSearchParams(initial));
  let selectedId = $state<string | null>(initial.get("id"));
  let tab = $state(initial.get("tab") ?? "email");
  let sideOpen = $state(typeof window === "undefined" || window.innerWidth > 900);

  let items = $state<ListItem[]>([]);
  let total = $state(0);
  let facets = $state<Facets | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Typing waits briefly before querying; every other change queries at once.
  let query = $state<FilterState>(fromSearchParams(initial));
  let typingTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const next = $state.snapshot(filters) as FilterState;
    clearTimeout(typingTimer);
    if (next.q !== query.q) typingTimer = setTimeout(() => (query = next), 200);
    else query = next;
  });

  $effect(() => {
    const f = query;
    const ctrl = new AbortController();
    loading = true;
    Promise.all([fetchList(f, ctrl.signal), fetchFacets(f, ctrl.signal)])
      .then(([list, counts]) => {
        items = list.items;
        total = list.total;
        facets = counts;
        error = null;
        if (!selectedId && items.length) selectedId = items[0].source_file;
      })
      .catch((e: Error) => { if (e.name !== "AbortError") error = e.message; })
      .finally(() => { if (!ctrl.signal.aborted) loading = false; });
    return () => ctrl.abort();
  });

  $effect(() => {
    const qs = toSearchParams(filters, { id: selectedId, tab: tab === "email" ? null : tab }).toString();
    history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
  });

  onMount(() => {
    const onPop = () => {
      const p = new URLSearchParams(location.search);
      filters = fromSearchParams(p);
      selectedId = p.get("id");
    };
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  });

  const selected = $derived(items.find((i) => i.source_file === selectedId) ?? null);

  const onToggle = (facet: FacetKey, value: string) => (filters = toggle(filters, facet, value));
  const select = (id: string) => { selectedId = id; tab = "email"; };
</script>

<div class="app">
  <header class="top">
    <a class="brand" href="/" aria-label="Compu.J Market Research home">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#BFD8FF" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17h10.5a3.5 3.5 0 0 0 .4-6.98A5.5 5.5 0 0 0 7.3 9.1 4 4 0 0 0 7 17z"></path><path d="M10 20.2a3 3 0 0 1 4 0"></path></svg>
      <span class="name">Compu.J</span><span class="slash">/</span><span class="area">Market Research</span>
    </a>
    <span class="divider"></span>
    <Ticker />
  </header>

  <main class="main">
    {#if sideOpen}
      <FilterSidebar
        {filters} {facets} {onToggle}
        onClear={(f) => (filters = clearFacet(filters, f))}
        onClearAll={() => (filters = clearAll(filters))}
        onCollapse={() => (sideOpen = false)}
      />
    {:else}
      <CollapsedRail selected={filters.asset} active={activeCount(filters)}
        onToggle={(t) => onToggle("asset", t)} onExpand={() => (sideOpen = true)} />
    {/if}
    <NoteList
      {filters} {items} {total} {loading} {error} {selectedId}
      onSearch={(q) => (filters = { ...filters, q })}
      onSort={(sort: Sort) => (filters = { ...filters, sort })}
      onRemove={onToggle}
      onSelect={select}
    />
    <Viewer record={selected} {tab} onTab={(t) => (tab = t)} />
  </main>
</div>

<style>
  .app { height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  .top {
    display: flex; align-items: center; gap: 12px; height: 44px; padding: 0 16px; flex-shrink: 0;
    border-bottom: 1px solid var(--border); background: linear-gradient(90deg, #17181c, #0b0b0d 40%);
  }
  .brand { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .name { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
  .slash { color: var(--faint); }
  .area { color: var(--text-3); }
  .divider { width: 1px; height: 20px; background: rgba(255, 255, 255, 0.12); flex-shrink: 0; }
  .main { flex: 1 1 auto; display: flex; min-height: 0; }
  @media (max-width: 900px) {
    .app { height: auto; min-height: 100vh; overflow: visible; }
    .area, .slash { display: none; }
    .main { flex-direction: column; }
    .main :global(.sidebar), .main :global(.rail) { flex-basis: auto; max-height: 50vh; border-right: 0; border-bottom: 1px solid var(--border); }
    .main :global(.rail) { flex-direction: row; justify-content: center; flex-wrap: wrap; padding: 8px; }
    .main :global(.list) { min-width: 0; max-height: 70vh; border-right: 0; }
  }
</style>
