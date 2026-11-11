<script lang="ts">
  // Folded sidebar: asset-class quick toggles and the active-filter count.
  import { TAXONOMY, classColour } from "../lib/taxonomy.ts";

  type Props = { selected: string[]; active: number; onToggle: (tag: string) => void; onExpand: () => void };
  let { selected, active, onToggle, onExpand }: Props = $props();
</script>

<aside class="rail" aria-label="Filters (collapsed)">
  <button type="button" class="open hv" aria-label="Expand filters" title="Expand filters" onclick={onExpand}>
    <span class="ms" aria-hidden="true">left_panel_open</span>
    {#if active}<span class="badge">{active}</span>{/if}
  </button>
  <span class="rule"></span>
  {#each TAXONOMY as [primary, , icon]}
    {@const on = selected.includes(primary)}
    {@const k = classColour(primary)}
    <button
      type="button" class="ws hv" class:on aria-pressed={on} aria-label="Filter {primary}" title={primary}
      style:background={on ? k.accent : "transparent"} style:color={on ? k.onAccent : k.accent}
      onclick={() => onToggle(primary)}
    >
      <span class="ms" class:fill={on} aria-hidden="true">{icon}</span>
    </button>
  {/each}
</aside>

<style>
  .rail {
    flex: 0 0 52px; border-right: 1px solid var(--border); padding: 10px 0; display: flex;
    flex-direction: column; align-items: center; gap: 8px; background: var(--panel);
  }
  .open {
    position: relative; width: 32px; height: 32px; border: 1px solid var(--border-strong); border-radius: 8px;
    background: transparent; color: var(--text-2); display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 0;
  }
  .badge {
    position: absolute; top: -5px; right: -5px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px;
    background: var(--magenta); color: #fff; font-size: 10px; font-weight: 600; display: inline-flex; align-items: center; justify-content: center;
  }
  .rule { width: 20px; height: 1px; background: var(--border); }
  .ws { width: 32px; height: 32px; border: 0; padding: 0; cursor: pointer; display: flex; align-items: center; justify-content: center; border-radius: 16px; transition: border-radius 160ms; }
  .ws.on { border-radius: 9px; }
</style>
