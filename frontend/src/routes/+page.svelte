<script lang="ts">
  import { onMount } from 'svelte';
  import { getStatus, getUsage, createTask, type Task, type UsageEntry } from '$lib/api';

  let status = 'loading…';
  let taskId = '';
  let usage: UsageEntry[] = [];
  let newTask = '';
  let error = '';
  let submitting = false;

  async function refresh() {
    try {
      const s = await getStatus();
      status = s.status;
      taskId = s.task_id;
      const u = await getUsage();
      usage = u.usage;
    } catch (e: any) {
      error = e.message;
    }
  }

  async function submitTask() {
    if (!newTask.trim()) return;
    submitting = true;
    error = '';
    try {
      const res = await createTask(newTask.trim());
      taskId = res.task_id;
      newTask = '';
      await refresh();
    } catch (e: any) {
      error = e.message;
    } finally {
      submitting = false;
    }
  }

  onMount(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  });

  function statusClass(s: string) {
    if (s === 'idle' || s === 'done') return 'status-idle';
    if (s.startsWith('halted')) return 'status-halted';
    return 'status-active';
  }
</script>

<h1>AutoDev</h1>

<section class="status-card">
  <div class="status-row">
    <span class="label">Agent status</span>
    <span class="badge {statusClass(status)}">{status}</span>
  </div>
  {#if taskId}
    <div class="status-row">
      <span class="label">Current task</span>
      <a href="/plan/{taskId}">{taskId}</a>
    </div>
  {/if}
</section>

{#if status === 'idle' || status === 'done'}
  <section class="new-task">
    <h2>New Task</h2>
    <textarea
      bind:value={newTask}
      placeholder="Describe what you want AutoDev to build or fix…"
      rows="4"
    ></textarea>
    <button on:click={submitTask} disabled={submitting || !newTask.trim()}>
      {submitting ? 'Submitting…' : 'Start Task'}
    </button>
  </section>
{:else if status === 'awaiting_plan_review'}
  <section class="action-prompt">
    <a href="/plan/{taskId}" class="btn">Review Plan →</a>
  </section>
{:else if status === 'coding'}
  <section class="action-prompt">
    <a href="/log/{taskId}" class="btn">Watch Live Log →</a>
  </section>
{:else if status === 'awaiting_diff_review'}
  <section class="action-prompt">
    <a href="/diff/{taskId}" class="btn">Review Diff →</a>
  </section>
{:else if status.startsWith('halted')}
  <section class="halted-alert">
    <strong>Agent halted.</strong>
    {#if status === 'halted:credits_exhausted'}
      <p>Daily credits exhausted. You can review the partial diff or wait until tomorrow.</p>
      <div class="halted-actions">
        <a href="/diff/{taskId}" class="btn btn-secondary">Review Partial Diff</a>
      </div>
    {:else}
      <p>Check the task detail for the halt reason.</p>
      <a href="/plan/{taskId}" class="btn btn-secondary">View Task →</a>
    {/if}
  </section>
{/if}

{#if error}
  <p class="error">{error}</p>
{/if}

{#if usage.length > 0}
  <section class="usage">
    <h2>Today's Token Usage</h2>
    <table>
      <thead><tr><th>Provider</th><th>Tokens Used</th></tr></thead>
      <tbody>
        {#each usage as row}
          <tr>
            <td>{row.provider}</td>
            <td>{row.tokens_used.toLocaleString()}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{/if}

<style>
  h1 { font-size: 1.8rem; margin-bottom: 1.5rem; }
  h2 { font-size: 1.1rem; margin-bottom: 0.75rem; color: #8b949e; }

  .status-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
  }
  .status-row {
    display: flex;
    gap: 1rem;
    align-items: center;
    padding: 0.25rem 0;
  }
  .label { color: #8b949e; font-size: 0.9rem; min-width: 120px; }

  .badge {
    padding: 0.2em 0.65em;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
  }
  .status-idle    { background: #21262d; color: #8b949e; }
  .status-active  { background: #1f6feb33; color: #58a6ff; }
  .status-halted  { background: #da3633; color: #fff; }

  .new-task {
    margin-bottom: 1.5rem;
  }
  textarea {
    width: 100%;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e6edf3;
    padding: 0.75rem;
    font-size: 0.95rem;
    resize: vertical;
    margin-bottom: 0.75rem;
  }
  button, .btn {
    display: inline-block;
    background: #238636;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 0.5rem 1.25rem;
    font-size: 0.95rem;
    font-weight: 600;
    transition: background 0.15s;
  }
  button:hover:not(:disabled), .btn:hover { background: #2ea043; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: #21262d; border: 1px solid #30363d; }
  .btn-secondary:hover { background: #30363d; }

  .action-prompt, .halted-alert { margin-bottom: 1.5rem; }
  .halted-alert {
    background: #da363322;
    border: 1px solid #da3633;
    border-radius: 8px;
    padding: 1rem 1.25rem;
  }
  .halted-actions { margin-top: 0.75rem; display: flex; gap: 0.75rem; }

  .error { color: #f85149; font-size: 0.9rem; }

  .usage table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  .usage th, .usage td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #21262d;
  }
  .usage th { color: #8b949e; }
</style>
