<script lang="ts">
  // News ticker: live headlines from news.json, scrolling, paused on hover or focus.
  import { onMount } from "svelte";
  import { fetchNews, type News } from "../lib/api.ts";
  import { clock } from "../lib/format.ts";

  let news = $state<News>({ updated_at: null, source: null, items: [] });
  let failed = $state(false);

  async function load() {
    try {
      news = await fetchNews();
      failed = false;
    } catch {
      failed = true;
    }
  }

  onMount(() => {
    load();
    const timer = setInterval(load, 60_000); // the file refreshes every 10 min; poll cheaply
    return () => clearInterval(timer);
  });

  // Roughly constant reading speed whatever the number of headlines.
  const duration = $derived(Math.max(40, news.items.length * 7));
</script>

<div class="ticker" aria-label="Market headlines">
  <span class="live"><span class="dot"></span>LIVE</span>
  <div class="viewport">
    {#if news.items.length}
      <div class="track" style:animation-duration="{duration}s">
        {#each [0, 1] as copy}
          <ul class="run" aria-hidden={copy === 1}>
            {#each news.items as h}
              <li>
                <a class="headline" href={h.url} target="_blank" rel="noopener noreferrer" tabindex={copy === 1 ? -1 : 0}>
                  <span class="time mono">{clock(h.published_at)}</span>
                  <span>{h.title}</span>
                  <span class="source">{h.source}</span>
                </a>
              </li>
            {/each}
          </ul>
        {/each}
      </div>
    {:else}
      <span class="empty">{failed ? "Headlines unavailable" : "Waiting for headlines. Run `bun run news`."}</span>
    {/if}
  </div>
</div>
<span class="updated" title={news.source ? `Source: ${news.source}` : undefined}>
  Updated <span class="mono">{clock(news.updated_at)}</span> · every 10 min
</span>

<style>
  .ticker { flex: 1 1 auto; min-width: 0; display: flex; align-items: center; gap: 10px; }
  .live { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; color: var(--magenta); flex-shrink: 0; }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--magenta); animation: pulse 2s ease-in-out infinite; }
  .viewport {
    flex: 1 1 auto; overflow: hidden; min-width: 0;
    mask-image: linear-gradient(90deg, transparent, #000 16px, #000 calc(100% - 16px), transparent);
  }
  .track { display: flex; width: max-content; animation: scroll linear infinite; }
  .ticker:hover .track, .ticker:focus-within .track { animation-play-state: paused; }
  .run { display: flex; align-items: center; gap: 24px; padding: 0 24px 0 0; margin: 0; list-style: none; }
  .headline { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; font-size: 12.5px; color: var(--text-2); }
  .headline:hover { text-decoration: underline; text-underline-offset: 3px; }
  .time, .source { font-size: 11px; color: var(--muted); }
  .empty { font-size: 12px; color: var(--muted); }
  .updated { font-size: 11.5px; color: var(--muted); white-space: nowrap; flex-shrink: 0; }
  .updated .mono { color: var(--text-2); }
  @keyframes scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
  @media (max-width: 700px) { .updated { display: none; } }
</style>
