<script lang="ts">
  import { onMount } from 'svelte';
  import { getLogs } from '$lib/api';

  let lines: string[] = [];
  let loading = true;
  let error = '';
  let lineCount = 200;

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await getLogs(lineCount);
      lines = res.lines;
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

{#if error}
  <p class="error">{error}</p>
{/if}

{#if loading}
  <p class="muted">Loading…</p>
{:else if lines.length === 0}
  <p class="muted">No log entries yet.</p>
{:else}
  <pre class="log-output">{lines.join('\n')}</pre>
{/if}

<style>
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  h1 { font-size: 1.5rem; }
  .controls { display: flex; gap: 0.75rem; align-items: center; }
  select {
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
  .log-output {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem;
    font-size: 0.78rem;
    color: #8b949e;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 80vh;
    overflow-y: auto;
  }
  .muted { color: #8b949e; }
  .error { color: #f85149; }
</style>
