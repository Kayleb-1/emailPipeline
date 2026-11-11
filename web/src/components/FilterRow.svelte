<script lang="ts">
  // One filter option: tickbox, label, count and a distribution bar (v3/v5 filter block).
  type Props = {
    label: string;
    n: number;
    max: number;
    on: boolean;
    onToggle: () => void;
    indent?: boolean;
    icon?: string;
    iconColor?: string;
    fill?: string;
    barIdle?: string;
    subs?: { open: boolean; onExpand: () => void } | null;
  };
  let { label, n, max, on, onToggle, indent = false, icon, iconColor = "#A1A1AA",
        fill = "var(--grad)", barIdle = "rgba(255,255,255,.28)", subs = null }: Props = $props();
  const pct = $derived(Math.round((n / Math.max(1, max)) * 100));
</script>

<div class="wrap">
  <button type="button" class="row hv" class:on class:indent class:zero={n === 0 && !on} aria-pressed={on} onclick={onToggle}>
    <span class="box" style:background={on ? fill : "transparent"}>
      {#if on}<span class="ms" aria-hidden="true">check</span>{/if}
    </span>
    {#if icon}<span class="ms icon" aria-hidden="true" style:color={iconColor}>{icon}</span>{/if}
    <span class="body">
      <span class="top"><span class="text">{label}</span><span class="n mono">{n}</span></span>
      <span class="bar"><span style:width="{pct}%" style:background={on ? fill : barIdle}></span></span>
    </span>
  </button>
  {#if subs}
    <button type="button" class="caret hv" aria-expanded={subs.open} aria-label="{subs.open ? 'Collapse' : 'Expand'} {label}" onclick={subs.onExpand}>
      <span class="ms" aria-hidden="true">{subs.open ? "expand_less" : "expand_more"}</span>
    </button>
  {:else}
    <span class="pad"></span>
  {/if}
</div>

<style>
  .wrap { display: flex; align-items: center; gap: 2px; }
  .row {
    flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; min-height: 34px;
    padding: 4px 6px; border: 0; border-radius: 8px; background: transparent; cursor: pointer; text-align: left;
  }
  .row.indent { padding-left: 34px; }
  .row.on { background: rgba(255, 255, 255, 0.06); }
  .row.zero { opacity: 0.45; }
  .box {
    width: 14px; height: 14px; flex-shrink: 0; border-radius: 4px; display: inline-flex;
    align-items: center; justify-content: center; color: #fff; border: 1.5px solid rgba(255, 255, 255, 0.32);
  }
  .on .box { border: 0; }
  .box .ms { font-size: 12px; font-variation-settings: "wght" 600; }
  .icon { font-size: 16px; }
  .body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .top { display: flex; justify-content: space-between; gap: 8px; }
  .text { font-size: 12.5px; font-weight: 500; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .indent .text { font-size: 12px; font-weight: 400; color: var(--text-3); }
  .on .text { color: #fff; }
  .n { font-size: 11px; color: var(--muted); }
  .bar { height: 3px; border-radius: 2px; background: rgba(255, 255, 255, 0.07); overflow: hidden; }
  .bar span { display: block; height: 3px; border-radius: 2px; }
  .caret, .pad { width: 26px; height: 26px; flex-shrink: 0; }
  .caret { border: 0; border-radius: 6px; background: transparent; color: var(--muted); display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 0; }
  .caret .ms { font-size: 16px; }
</style>
