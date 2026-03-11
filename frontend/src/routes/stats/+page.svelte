<script lang="ts">
  import { onMount } from 'svelte';
  import { getStats, type StatsResponse } from '$lib/api';

  let stats: StatsResponse | null = null;
  let loading = true;
  let error = '';

  async function load() {
    loading = true;
    error = '';
    try {
      stats = await getStats();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(load);

  // Group daily_history by date for the table
  $: dailyByDate = (() => {
    if (!stats) return [];
    const map = new Map<string, Record<string, number>>();
    for (const row of stats.daily_history) {
      if (!map.has(row.date)) map.set(row.date, {});
      map.get(row.date)![row.provider] = row.tokens_used;
    }
    // return sorted desc by date
    return [...map.entries()]
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([date, byProvider]) => ({ date, byProvider }));
  })();

  $: providers = stats ? Object.keys(stats.providers_config) : [];

  function budgetPct(provider: string, tokens: number): number {
    const budget = stats?.providers_config[provider]?.daily_token_budget ?? 0;
    if (!budget) return 0;
    return Math.min(100, (tokens / budget) * 100);
  }
</script>

<div class="header">
  <h1>Agent Statistics</h1>
  <button on:click={load} disabled={loading}>↻ Refresh</button>
</div>

{#if error}
  <p class="error">{error}</p>
{/if}

{#if loading}
  <p class="muted">Loading…</p>
{:else if stats}

  <!-- All-time totals -->
  <section class="card">
    <h2>All-Time Token Usage by Provider</h2>
    {#if stats.totals_by_provider.length === 0}
      <p class="muted">No usage recorded yet.</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Model</th>
            <th>Total Tokens</th>
            <th>Days Active</th>
            <th>Daily Budget</th>
          </tr>
        </thead>
        <tbody>
          {#each stats.totals_by_provider as row}
            {@const cfg = stats.providers_config[row.provider]}
            <tr>
              <td class="provider-name">{row.provider}</td>
              <td class="mono muted">{cfg?.model ?? '—'}</td>
              <td>{row.total_tokens.toLocaleString()}</td>
              <td>{row.days_active}</td>
              <td>{cfg?.daily_token_budget?.toLocaleString() ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  <!-- Daily breakdown -->
  <section class="card">
    <h2>Daily Breakdown</h2>
    {#if dailyByDate.length === 0}
      <p class="muted">No daily records yet.</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>Date</th>
            {#each providers as p}<th>{p}</th>{/each}
          </tr>
        </thead>
        <tbody>
          {#each dailyByDate as row}
            <tr>
              <td class="mono">{row.date}</td>
              {#each providers as p}
                {@const tokens = row.byProvider[p] ?? 0}
                {@const pct = budgetPct(p, tokens)}
                <td>
                  {#if tokens > 0}
                    <span class="token-cell" class:warn={pct >= 80} class:danger={pct >= 95}>
                      {tokens.toLocaleString()}
                      {#if pct > 0}
                        <span class="pct">({pct.toFixed(0)}%)</span>
                      {/if}
                    </span>
                  {:else}
                    <span class="muted">—</span>
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

{/if}

<style>
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }
  h1 { font-size: 1.5rem; }
  h2 { font-size: 1.05rem; color: #8b949e; margin-bottom: 0.75rem; }

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

  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1.1rem 1.25rem;
    margin-bottom: 1.5rem;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
  }
  th, td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #21262d;
    white-space: nowrap;
  }
  th { color: #8b949e; font-weight: 600; }
  tr:last-child td { border-bottom: none; }

  .provider-name { font-weight: 600; color: #e6edf3; }
  .mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.82rem; }
  .muted { color: #6e7681; }

  .token-cell { color: #e6edf3; }
  .token-cell.warn   { color: #d29922; }
  .token-cell.danger { color: #f85149; }
  .pct { font-size: 0.8rem; color: #8b949e; margin-left: 0.2rem; }

  .error { color: #f85149; font-size: 0.9rem; }
</style>
