<script lang="ts">
  // Research list: search, active filter chips, sort, and one row per email.
  import type { ListItem } from "../lib/api.ts";
  import { chips as chipList, type FacetKey, type FilterState, type Sort } from "../lib/filters.ts";
  import { dateShort, snippetParts } from "../lib/format.ts";
  import { classColour, iconFor } from "../lib/taxonomy.ts";

  type Props = {
    filters: FilterState;
    items: ListItem[];
    total: number;
    loading: boolean;
    error: string | null;
    selectedId: string | null;
    onSearch: (q: string) => void;
    onSort: (s: Sort) => void;
    onRemove: (facet: FacetKey, value: string) => void;
    onSelect: (id: string) => void;
  };
  let { filters, items, total, loading, error, selectedId, onSearch, onSort, onRemove, onSelect }: Props = $props();

  const chips = $derived(chipList(filters));
  let listEl: HTMLDivElement | undefined = $state();

  // Up/down arrows move the selection through the list.
  function onKey(e: KeyboardEvent) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const i = items.findIndex((it) => it.source_file === selectedId);
    const next = items[Math.min(items.length - 1, Math.max(0, i + (e.key === "ArrowDown" ? 1 : -1)))];
    if (next) {
      onSelect(next.source_file);
      listEl?.querySelector<HTMLButtonElement>(`[data-id="${CSS.escape(next.source_file)}"]`)?.focus();
    }
  }
</script>

<section class="list" aria-label="Research list">
  <div class="bar">
    <h1>Notes</h1>
    <span class="count mono" aria-live="polite">{items.length}/{total}</span>
    <div class="seg" role="radiogroup" aria-label="Sort">
      {#each [["new", "Newest"], ["old", "Oldest"]] as [key, label]}
        <button type="button" role="radio" aria-checked={filters.sort === key} class:on={filters.sort === key} onclick={() => onSort(key as Sort)}>{label}</button>
      {/each}
    </div>
  </div>

  <div class="tools">
    <label class="search">
      <span class="ms" aria-hidden="true">search</span>
      <span class="sr-only">Search research</span>
      <input type="search" value={filters.q} oninput={(e) => onSearch(e.currentTarget.value)}
             placeholder="Search notes, banks, companies, full text" />
    </label>
    {#if chips.length}
      <div class="chips">
        {#each chips as c (c.facet + c.value)}
          {@const k = c.tag ? classColour(c.tag) : null}
          <span class="chip" class:plain={!k} style:background={k?.bg} style:color={k?.fg}>
            {#if c.tag}<span class="ms" aria-hidden="true">{iconFor(c.tag)}</span>{/if}
            <span class="pre">{c.prefix}</span>{c.label}
            <button type="button" class="x hv" aria-label="Remove filter {c.label}" onclick={() => onRemove(c.facet, c.value)}>
              <span class="ms" aria-hidden="true">close</span>
            </button>
          </span>
        {/each}
      </div>
    {/if}
  </div>

  <div class="rows scroll" class:dim={loading} bind:this={listEl} onkeydown={onKey} role="presentation">
    {#if error}
      <div class="empty"><strong>Couldn't load notes</strong><span>{error}</span></div>
    {:else if !items.length && !loading}
      <div class="empty"><strong>No notes match</strong><span>Remove a filter or change the search.</span></div>
    {/if}
    {#each items as it (it.source_file)}
      {@const sel = it.source_file === selectedId}
      {@const k = classColour(it.primary_asset_tag)}
      <button type="button" class="row hv" class:sel data-id={it.source_file} aria-current={sel} onclick={() => onSelect(it.source_file)}>
        <span class="icon" style:background={sel ? k.accent : k.bg} style:color={sel ? k.onAccent : k.fg}>
          <span class="ms" class:fill={sel} aria-hidden="true">{iconFor(it.primary_asset_tag)}</span>
        </span>
        <span class="body">
          <span class="meta">
            <span class="bank">{it.bank}</span>
            {#if it.pdf_attachment}<span class="ms clip" role="img" aria-label="Has PDF">attach_file</span>{/if}
            <span class="date mono">{dateShort(it.date)}</span>
          </span>
          <span class="title">{it.folder_name}</span>
          {#if it.snippet}
            <span class="snippet">
              {#each snippetParts(it.snippet) as part}{#if part.hit}<mark>{part.text}</mark>{:else}{part.text}{/if}{/each}
            </span>
          {/if}
          <span class="tags">
            <span class="pill" style:background={k.bg} style:color={k.fg}>{it.primary_asset_tag}</span>
            {#each it.asset_tags.filter((t) => t !== it.primary_asset_tag) as t}
              <span class="pill outline">{t}</span>
            {/each}
          </span>
        </span>
      </button>
    {/each}
  </div>
</section>

<style>
  .list { flex: 1 1 340px; min-width: 300px; display: flex; flex-direction: column; border-right: 1px solid var(--border); background: var(--list); min-height: 0; }
  .bar { display: flex; align-items: center; gap: 8px; height: 48px; padding: 0 14px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
  h1 { margin: 0; font-size: 16px; font-weight: 600; letter-spacing: -0.01em; }
  .count { font-size: 11.5px; color: var(--muted); }
  .seg { margin-left: auto; display: inline-flex; height: 28px; padding: 2px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.12); }
  .seg button { height: 22px; padding: 0 8px; border: 0; border-radius: 6px; font-size: 11.5px; cursor: pointer; background: transparent; color: var(--muted); }
  .seg button.on { background: rgba(255, 255, 255, 0.12); color: var(--text); }
  .tools { padding: 10px 14px; display: flex; flex-direction: column; gap: 8px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
  .search { display: flex; align-items: center; gap: 8px; height: 34px; padding: 0 6px 0 10px; border-radius: 8px; border: 1px solid var(--border-strong); background: var(--field); cursor: text; }
  .search .ms { color: var(--muted); }
  .search input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--text); font: inherit; font-size: 13px; }
  .search input::placeholder { color: #7c7c85; }
  .search:focus-within { border-color: rgba(240, 40, 127, 0.6); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { display: inline-flex; align-items: center; gap: 4px; height: 24px; padding: 0 2px 0 8px; border-radius: 6px; font-size: 12px; }
  .chip.plain { border: 1px solid rgba(240, 40, 127, 0.45); background: rgba(240, 40, 127, 0.1); color: var(--pink); }
  .chip .ms { font-size: 14px; }
  .pre { opacity: 0.7; }
  .x { width: 20px; height: 20px; border: 0; border-radius: 4px; background: transparent; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; padding: 0; color: inherit; }
  .rows { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 10px 14px; display: flex; flex-direction: column; gap: 6px; transition: opacity 120ms; }
  .rows.dim { opacity: 0.6; }
  .row {
    width: 100%; display: flex; align-items: flex-start; gap: 10px; padding: 9px 10px; cursor: pointer;
    border-radius: 8px; border: 1px solid var(--border); background: transparent; text-align: left;
  }
  .row.sel { border-color: rgba(240, 40, 127, 0.65); background: linear-gradient(90deg, rgba(240, 40, 127, 0.14), rgba(139, 63, 224, 0.06)); }
  .icon { width: 30px; height: 30px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; }
  .icon .ms { font-size: 17px; }
  .body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .meta { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--muted); }
  .bank { color: var(--text-3); font-weight: 500; }
  .clip { font-size: 14px; }
  .date { margin-left: auto; font-size: 11px; }
  .title { font-size: 13px; font-weight: 500; line-height: 1.35; color: var(--text); }
  .snippet { font-size: 11.5px; line-height: 1.4; color: var(--muted); display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  mark { background: rgba(240, 40, 127, 0.22); color: var(--pink); border-radius: 3px; padding: 0 2px; }
  .tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
  .empty { padding: 40px 16px; text-align: center; color: var(--muted); display: flex; flex-direction: column; gap: 4px; }
  .empty strong { font-size: 14px; font-weight: 500; color: var(--text); }
</style>
