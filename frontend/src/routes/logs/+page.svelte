<script lang="ts">
  import { onMount, afterUpdate } from 'svelte';
  import { getLogs } from '$lib/api';

  type Level = 'ALL' | 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

  interface ParsedLine {
    raw: string;
    level: Level;
    date: string; // YYYY-MM-DD extracted from timestamp, or '' if unparseable
  }

  let allLines: ParsedLine[] = [];
  let loading = true;
  let error = '';
  let lineCount = 500;
  let activeLevel: Level = 'ALL';
  let activeDate = 'ALL';
  let logEl: HTMLElement;
  let shouldScroll = true;

  const LEVELS: Level[] = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR'];

  const DATE_RE = /^(\d{4}-\d{2}-\d{2})/;

  function parseLevel(line: string): Level {
    if (/\bERROR\b/.test(line))   return 'ERROR';
    if (/\bWARNING\b/.test(line)) return 'WARNING';
    if (/\bINFO\b/.test(line))    return 'INFO';
    if (/\bDEBUG\b/.test(line))   return 'DEBUG';
    return 'INFO';
  }

  function parseDate(line: string): string {
    const m = line.match(DATE_RE);
    return m ? m[1] : '';
  }

  function levelClass(level: Level): string {
    return `line-${level.toLowerCase()}`;
  }

  $: uniqueDates = (() => {
    const seen = new Set<string>();
    for (const l of allLines) if (l.date) seen.add(l.date);
    return [...seen].sort().reverse(); // most recent first
  })();

  $: filteredLines = allLines.filter(l => {
    if (activeLevel !== 'ALL' && l.level !== activeLevel) return false;
    if (activeDate !== 'ALL' && l.date !== activeDate) return false;
    return true;
  });

  // Scroll to bottom after each render when new content arrives
  afterUpdate(() => {
    if (shouldScroll && logEl) {
      logEl.scrollTop = logEl.scrollHeight;
    }
  });

  async function load() {
    loading = true;
    error = '';
    shouldScroll = true;
    try {
      const res = await getLogs(lineCount);
      allLines = res.lines.map(raw => ({ raw, level: parseLevel(raw), date: parseDate(raw) }));
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="header">
  <h1>Agent Logs</h1>
  <div class="controls">
    <select bind:value={lineCount} on:change={load}>
      <option value={100}>Last 100 lines</option>
      <option value={200}>Last 200 lines</option>
      <option value={500}>Last 500 lines</option>
      <option value={1000}>Last 1000 lines</option>
    </select>
    <button on:click={load} disabled={loading}>↻ Refresh</button>
  </div>
</div>

<div class="filter-row">
  <div class="level-filters">
    {#each LEVELS as lvl}
      <button
        class="filter-btn filter-{lvl.toLowerCase()}"
        class:active={activeLevel === lvl}
        on:click={() => activeLevel = lvl}
      >
        {lvl}
        {#if lvl !== 'ALL'}
          <span class="count">{allLines.filter(l => l.level === lvl).length}</span>
        {/if}
      </button>
    {/each}
  </div>

  {#if uniqueDates.length > 0}
    <select class="date-select" bind:value={activeDate}>
      <option value="ALL">All dates</option>
      {#each uniqueDates as d}
        <option value={d}>{d}</option>
      {/each}
    </select>
  {/if}
</div>

{#if error}
  <p class="error">{error}</p>
{/if}

{#if loading}
  <p class="muted">Loading…</p>
{:else if filteredLines.length === 0}
  <p class="muted">No log entries{activeLevel !== 'ALL' ? ` at level ${activeLevel}` : ''}{activeDate !== 'ALL' ? ` on ${activeDate}` : ''} yet.</p>
{:else}
  <div class="log-output" bind:this={logEl} on:scroll={() => {
    // If user scrolls up, stop auto-scrolling; snap back on next load
    const atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 40;
    shouldScroll = atBottom;
  }}>
    {#each filteredLines as line}
      <div class="log-line {levelClass(line.level)}">{line.raw}</div>
    {/each}
  </div>
{/if}

<style>
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }
  h1 { font-size: 1.5rem; }
  .controls { display: flex; gap: 0.75rem; align-items: center; }
  select, .date-select {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e6edf3;
    padding: 0.35rem 0.65rem;
    font-size: 0.85rem;
  }
  button {
    background: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 0.35rem 0.85rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  button:hover:not(:disabled) { background: #30363d; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
  }
  .level-filters {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .filter-btn {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
    border-radius: 20px;
    opacity: 0.55;
    transition: opacity 0.15s, background 0.15s;
  }
  .filter-btn.active { opacity: 1; }
  .filter-btn:hover { opacity: 0.9; }

  .filter-all        { border-color: #30363d; }
  .filter-debug      { border-color: #444c56; color: #8b949e; }
  .filter-info       { border-color: #1f6feb; color: #58a6ff; }
  .filter-warning    { border-color: #9e6a03; color: #d29922; }
  .filter-error      { border-color: #b62324; color: #f85149; }

  .filter-all.active     { background: #21262d; }
  .filter-debug.active   { background: #21262d; }
  .filter-info.active    { background: #1f6feb22; }
  .filter-warning.active { background: #9e6a0322; }
  .filter-error.active   { background: #b6232422; }

  .count {
    background: #30363d;
    border-radius: 10px;
    padding: 0 0.4em;
    font-size: 0.75rem;
  }

  .log-output {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 0.78rem;
    overflow-x: auto;
    overflow-y: auto;
    height: calc(100vh - 230px);
    min-height: 400px;
  }
  .log-line {
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.55;
    padding: 0.05rem 0;
  }
  .line-debug   { color: #6e7681; }
  .line-info    { color: #8b949e; }
  .line-warning { color: #d29922; }
  .line-error   { color: #f85149; }

  .muted { color: #8b949e; }
  .error { color: #f85149; }
</style>
