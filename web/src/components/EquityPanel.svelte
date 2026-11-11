<script lang="ts">
  // Equity metadata: material companies and SECTOR > Subindustry strings.
  import { initials, splitIndustry } from "../lib/format.ts";
  import { classColour } from "../lib/taxonomy.ts";

  let { companies, industries }: { companies: string[]; industries: string[] } = $props();
</script>

<div class="card equity">
  <div class="head"><span class="ms fill" aria-hidden="true" style:color={classColour("Equity").accent}>candlestick_chart</span><h3>Equity</h3></div>
  <div class="block">
    <span class="label">Companies</span>
    {#each companies as name}
      <div class="company"><span class="avatar">{initials(name)}</span>{name}</div>
    {:else}
      <span class="none">None materially discussed</span>
    {/each}
  </div>
  <div class="rule"></div>
  <div class="block">
    <span class="label">Industry</span>
    {#each industries.length ? industries : ["Unknown"] as s}
      {@const ind = splitIndustry(s)}
      <div class="industry"><span class="sector">{ind.sector}</span><span class="sub">{ind.sub}</span></div>
    {/each}
  </div>
</div>

<style>
  .head { padding: 12px 14px 0; display: flex; align-items: center; gap: 6px; }
  h3 { margin: 0; font-size: 13px; font-weight: 600; }
  .head .ms { font-size: 18px; }
  .block { padding: 10px 14px; display: flex; flex-direction: column; gap: 6px; }
  .company { display: flex; align-items: center; gap: 8px; font-size: 13px; }
  .avatar { width: 24px; height: 24px; border-radius: 7px; background: var(--grad); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 700; flex-shrink: 0; }
  .none { font-size: 12px; color: var(--muted); }
  .rule { height: 1px; background: rgba(255, 255, 255, 0.08); }
  .industry { display: flex; flex-direction: column; }
  .sector { font-size: 10.5px; letter-spacing: 0.04em; color: var(--pink); }
  .sub { font-size: 13px; font-weight: 500; }
</style>
