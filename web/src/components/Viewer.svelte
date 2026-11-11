<script lang="ts">
  // Reader: header, Email/PDF tabs, the sandboxed email or the PDF, and the side cards.
  import { emailUrl, pdfUrl, type EmailRecord } from "../lib/api.ts";
  import { dateLong, initials } from "../lib/format.ts";
  import { classColour, iconFor } from "../lib/taxonomy.ts";
  import EquityPanel from "./EquityPanel.svelte";

  type Props = { record: EmailRecord | null; tab: string; onTab: (tab: string) => void };
  let { record, tab, onTab }: Props = $props();

  let remoteImages = $state(false);
  let stage: HTMLDivElement | undefined = $state();
  let isFull = $state(false);

  const pdfs = $derived(record?.pdf_attachment ?? []);
  const active = $derived(pdfs.includes(tab) ? tab : "email");
  const k = $derived(classColour(record?.primary_asset_tag ?? ""));
  const subs = $derived(record ? record.asset_tags.filter((t) => t !== record.primary_asset_tag) : []);

  async function toggleFull() {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await stage?.requestFullscreen?.();
  }
  $effect(() => {
    const sync = () => (isFull = document.fullscreenElement === stage);
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  });
</script>

  {#snippet tabs()}
    <div class="tabs" role="tablist" aria-label="Content">
      {#each [{ key: "email", label: "Email", icon: "mail" }, ...pdfs.map((p) => ({ key: p, label: p, icon: "picture_as_pdf" }))] as t}
        <button type="button" role="tab" aria-selected={active === t.key} class:on={active === t.key} onclick={() => onTab(t.key)}>
          <span class="ms" aria-hidden="true">{t.icon}</span><span class="tab-label">{t.label}</span>
        </button>
      {/each}
    </div>
  {/snippet}

<section class="viewer" aria-label="Research viewer">
  {#if record}
    <div class="toolbar">
      {@render tabs()}
      <div class="actions">
        {#if active === "email"}
          <span class="hint"><span class="ms" aria-hidden="true">shield</span>Sandboxed</span>
          <button type="button" class="btn hv" aria-pressed={remoteImages} onclick={() => (remoteImages = !remoteImages)}
                  title="Remote images can tell the sender you opened the email">
            <span class="ms" aria-hidden="true">{remoteImages ? "image" : "hide_image"}</span>
            {remoteImages ? "Remote images on" : "Load remote images"}
          </button>
        {:else}
          <a class="btn hv" href={pdfUrl(record.source_file, active)} target="_blank" rel="noopener"><span class="ms" aria-hidden="true">open_in_new</span>Open</a>
        {/if}
        <button type="button" class="btn accent hv" onclick={toggleFull}><span class="ms" aria-hidden="true">open_in_full</span>Full screen</button>
      </div>
    </div>

    <header class="head">
      <div class="who">
        <span class="bank-avatar">{initials(record.bank)}</span>
        <div class="who-text">
          <span class="bank">{record.bank}</span>
          <span class="source mono">{record.source_file}</span>
        </div>
        <span class="date mono">{dateLong(record.date)}</span>
      </div>
      <h2>{record.folder_name}</h2>
      <div class="tags">
        <span class="primary" style:background={k.bg} style:color={k.fg}>
          <span class="ms fill" aria-hidden="true">{iconFor(record.primary_asset_tag)}</span>{record.primary_asset_tag}
        </span>
        {#each subs as s}<span class="pill outline sub">{s}</span>{/each}
        {#if record.market_wrap === "YES"}<span class="wrap">Market wrap</span>{/if}
      </div>
    </header>

    <div class="content">
      <div class="stage" class:full={isFull} bind:this={stage}>
        {#if isFull}
          <div class="full-bar">
            <span class="primary" style:background={k.bg} style:color={k.fg}><span class="ms fill" aria-hidden="true">{iconFor(record.primary_asset_tag)}</span>{record.primary_asset_tag}</span>
            <span class="full-title">{record.folder_name}</span>
            <span class="full-meta">{record.bank} · {dateLong(record.date)}</span>
            {@render tabs()}
            <button type="button" class="btn hv" onclick={toggleFull}><span class="ms" aria-hidden="true">close_fullscreen</span>Exit <kbd>Esc</kbd></button>
          </div>
        {/if}
        {#key record.source_file + active + remoteImages}
          {#if active === "email"}
            <iframe class="frame email" title="Email: {record.folder_name}" src={emailUrl(record.source_file, remoteImages)}
                    sandbox="allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer" loading="lazy"></iframe>
          {:else}
            <iframe class="frame pdf" title="PDF: {active}" src={pdfUrl(record.source_file, active)}></iframe>
          {/if}
        {/key}
      </div>

      <aside class="side">
        {#if record.asset_tags.includes("Equity")}
          <EquityPanel companies={record.companies_mentioned} industries={record.industry_subindustry} />
        {/if}
        <div class="card pad">
          <h3>Attachments</h3>
          {#each pdfs as p}
            <button type="button" class="pdf-btn hv" class:on={active === p} onclick={() => onTab(p)}>
              <span class="ms" aria-hidden="true">picture_as_pdf</span><span class="mono">{p}</span>
            </button>
          {:else}
            <span class="none">No PDF attached</span>
          {/each}
        </div>
        <dl class="card pad details">
          <dt>Market wrap</dt><dd>{record.market_wrap}</dd>
          <dt>Primary</dt><dd>{record.primary_asset_tag}</dd>
          <dt>Date</dt><dd class="mono">{record.date ?? "null"}</dd>
          <dt>Source</dt><dd class="mono">{record.source_file}</dd>
        </dl>
      </aside>
    </div>
  {:else}
    <div class="placeholder">Select a note to read it</div>
  {/if}
</section>

<style>
  .viewer { flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; min-height: 0; overflow-y: auto;
    background: radial-gradient(120% 80% at 100% 0%, #1d1e23 0%, #0b0b0d 55%); }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-height: 48px; padding: 8px 16px; border-bottom: 1px solid var(--border); }
  .tabs { display: flex; flex-wrap: wrap; gap: 2px; padding: 3px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.12); background: rgba(8, 8, 10, 0.6); min-width: 0; }
  .tabs button { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border: 0; font-size: 12.5px; font-weight: 500; cursor: pointer; border-radius: 7px; background: transparent; color: #a1a1aa; max-width: 260px; }
  .tabs button.on { background: var(--grad); color: #fff; }
  .tabs .ms { font-size: 16px; }
  .tab-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .actions { margin-left: auto; display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); flex-wrap: wrap; }
  .hint { display: inline-flex; align-items: center; gap: 4px; }
  .hint .ms { font-size: 15px; }
  .head { padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; border-bottom: 1px solid var(--border); }
  .who { display: flex; align-items: center; gap: 10px; }
  .bank-avatar { width: 32px; height: 32px; border-radius: 9px; border: 1px solid var(--border-strong); background: linear-gradient(145deg, #26272c, #0f0f12); display: inline-flex; align-items: center; justify-content: center; font-size: 11.5px; font-weight: 600; flex-shrink: 0; }
  .who-text { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
  .bank { font-size: 13px; font-weight: 600; }
  .source { font-size: 11px; color: var(--muted); }
  .date { margin-left: auto; font-size: 11.5px; color: var(--muted); white-space: nowrap; }
  h2 { margin: 0; font-size: 19px; line-height: 1.3; font-weight: 600; letter-spacing: -0.01em; }
  .tags { display: flex; flex-wrap: wrap; gap: 6px; }
  .primary { display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 8px 0 6px; border-radius: 6px; font-size: 12px; font-weight: 600; flex-shrink: 0; }
  .primary .ms { font-size: 15px; }
  .sub { height: 24px; font-size: 12px; color: var(--text-3); }
  .wrap { height: 24px; padding: 0 8px; border-radius: 6px; background: var(--grad); color: #fff; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; }
  .content { flex: 1 1 auto; display: flex; flex-wrap: wrap; gap: 14px; padding: 14px 16px; align-items: flex-start; }
  .stage { flex: 999 1 420px; min-width: 0; height: max(560px, calc(100vh - 290px)); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.12); overflow: hidden; display: flex; flex-direction: column; background: #fff; }
  .stage.full { height: 100vh; border-radius: 0; border: 0; background: var(--bg); padding: 0 12px 12px; gap: 12px; }
  .full-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; min-height: 48px; padding: 8px 4px 0; color: var(--text); }
  .full-title { font-size: 14px; font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 200px; }
  .full-meta { font-size: 12px; color: var(--muted); }
  kbd { font-family: var(--mono); font-size: 10.5px; color: var(--muted); border: 1px solid var(--border-strong); border-radius: 4px; padding: 1px 4px; }
  .frame { flex: 1; width: 100%; border: 0; background: #fff; }
  .stage.full .frame { border-radius: 10px; }
  .frame.pdf { background: #1c1d21; }
  .side { flex: 1 1 240px; max-width: 100%; display: flex; flex-direction: column; gap: 12px; }
  .pad { padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; }
  h3 { margin: 0; font-size: 13px; font-weight: 600; }
  .pdf-btn { width: 100%; display: flex; align-items: center; gap: 8px; min-height: 34px; padding: 6px 10px; border-radius: 8px; cursor: pointer; border: 1px solid rgba(255, 255, 255, 0.12); background: transparent; color: var(--text-2); text-align: left; }
  .pdf-btn.on { border-color: rgba(240, 40, 127, 0.6); background: rgba(240, 40, 127, 0.1); }
  .pdf-btn .mono { font-size: 11.5px; overflow-wrap: anywhere; }
  .none { font-size: 12px; color: var(--muted); }
  .details { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; font-size: 12px; margin: 0; }
  dt { color: var(--muted); }
  dd { margin: 0; font-weight: 500; overflow-wrap: anywhere; }
  dd.mono { font-size: 11.5px; font-weight: 400; }
  .placeholder { flex: 1; min-height: 400px; display: flex; align-items: center; justify-content: center; color: var(--muted); }
</style>
