<script lang="ts">
  import { onMount } from 'svelte';
  import {
    getStatus, getUsage, createTask, listIssues, refreshIssues, getSchedule,
    type UsageEntry, type GitHubIssue, type ScheduleInfo
  } from '$lib/api';

  let status = 'loading…';
  let taskId = '';
  let usage: UsageEntry[] = [];
  let issues: GitHubIssue[] = [];
  let schedule: ScheduleInfo | null = null;
  let newTask = '';
  let error = '';
  let submitting = false;
  let refreshing = false;

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

  async function loadSchedule() {
    try {
      schedule = await getSchedule();
    } catch {
      // ignore if not available
    }
  }

  async function loadIssues() {
    try {
      const res = await listIssues();
      issues = res.issues;
    } catch {
      // GitHub not configured — silently ignore
    }
  }

  async function doRefreshIssues() {
    refreshing = true;
    error = '';
    try {
      const res = await refreshIssues();
      issues = res.issues;
    } catch (e: any) {
      error = e.message;
    } finally {
      refreshing = false;
    }
  }

  async function submitTask(description = newTask.trim(), issue_number?: number) {
    if (!description) return;
    submitting = true;
    error = '';
    try {
      const res = await createTask(description, issue_number);
      taskId = res.task_id;
      newTask = '';
      await refresh();
    } catch (e: any) {
      error = e.message;
    } finally {
      submitting = false;
    }
  }

  async function startFromIssue(issue: GitHubIssue) {
    const description = `#${issue.number}: ${issue.title}\n\n${issue.body}`;
    await submitTask(description, issue.number);
  }

  onMount(() => {
    refresh();
    loadIssues();
    loadSchedule();
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
  {#if schedule}
    <div class="status-row">
      <span class="label">Next scheduled run</span>
      <span class="schedule-time">
        {#if schedule.next_run}
          {new Date(schedule.next_run).toLocaleString()} ({schedule.timezone})
        {:else if schedule.enabled}
          Scheduler starting…
        {:else}
          Scheduler disabled
        {/if}
      </span>
    </div>
  {/if}
  <div class="status-row card-links">
    <a href="/logs" class="text-link">View agent logs →</a>
  </div>
</section>

{#if status === 'idle' || status === 'done'}
  <section class="new-task">
    <h2>New Task</h2>
    <textarea
      bind:value={newTask}
      placeholder="Describe what you want AutoDev to build or fix…"
      rows="4"
    ></textarea>
    <button on:click={() => submitTask()} disabled={submitting || !newTask.trim()}>
      {submitting ? 'Submitting…' : 'Start Task'}
    </button>
  </section>

  {#if issues.length > 0 || refreshing}
    <section class="issues">
      <div class="issues-header">
        <h2>Open GitHub Issues</h2>
        <button class="btn btn-sm btn-secondary" on:click={doRefreshIssues} disabled={refreshing || submitting}>
          {refreshing ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>
      {#each issues as issue}
        <div class="issue-row">
          <div class="issue-meta">
            <span class="issue-number">#{issue.number}</span>
            <span class="issue-title">{issue.title}</span>
            {#each issue.labels as label}
              <span class="issue-label">{label}</span>
            {/each}
          </div>
          <button class="btn btn-sm" on:click={() => startFromIssue(issue)} disabled={submitting}>
            Start
          </button>
        </div>
      {/each}
    </section>
  {/if}
{:else if status === 'awaiting_plan_review'}
  <section class="action-prompt">
    <a href="/plan/{taskId}" class="btn">Review Plan →</a>
  </section>
{:else if status === 'coding' || status === 'awaiting_step_review'}
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

  .schedule-time { color: #e6edf3; font-size: 0.9rem; }
  .card-links { margin-top: 0.25rem; }
  .text-link { color: #58a6ff; font-size: 0.85rem; text-decoration: none; }
  .text-link:hover { text-decoration: underline; }

  .issues { margin-bottom: 1.5rem; }
  .issues-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }
  .issues-header h2 { margin-bottom: 0; }
  .issue-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid #21262d;
    gap: 1rem;
  }
  .issue-meta { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; flex: 1; min-width: 0; }
  .issue-number { color: #8b949e; font-size: 0.85rem; white-space: nowrap; }
  .issue-title { color: #e6edf3; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .issue-label {
    background: #1f6feb33;
    color: #58a6ff;
    border-radius: 12px;
    font-size: 0.75rem;
    padding: 0.1em 0.5em;
  }
  .btn-sm { padding: 0.3rem 0.75rem; font-size: 0.85rem; white-space: nowrap; }

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
