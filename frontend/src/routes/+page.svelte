<script lang="ts">
  import { onMount } from 'svelte';
  import {
    getStatus, getUsage, createTask, listIssues, refreshIssues, getSchedule, resetSession,
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
  let resetting = false;

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

  async function doReset() {
    resetting = true;
    error = '';
    try {
      await resetSession();
      await refresh();
    } catch (e: any) {
      error = e.message;
    } finally {
      resetting = false;
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

<div class="dashboard-grid">
  <!-- ── LEFT: main control column ── -->
  <div class="col-main">

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
        <a href="/stats" class="text-link">Agent statistics →</a>
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
            <button class="btn btn-secondary" on:click={doReset} disabled={resetting}>
              {resetting ? 'Resetting…' : '↺ Reset to Idle'}
            </button>
          </div>
        {:else}
          <p>Check the logs for the halt reason.</p>
          <div class="halted-actions">
            <a href="/logs" class="btn btn-secondary">View Logs →</a>
            <button class="btn btn-secondary" on:click={doReset} disabled={resetting}>
              {resetting ? 'Resetting…' : '↺ Reset to Idle'}
            </button>
          </div>
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

  </div>

  <!-- ── RIGHT: task queue column ── -->
  <div class="col-queue">
    <section class="queue-card">
      <div class="queue-header">
        <h2>Task Queue</h2>
        <button class="btn btn-sm btn-secondary" on:click={doRefreshIssues} disabled={refreshing || submitting}>
          {refreshing ? '…' : '↻'}
        </button>
      </div>
      <p class="queue-sub">Issues the agent will tackle in order</p>

      {#if issues.length === 0}
        <p class="muted queue-empty">
          {refreshing ? 'Fetching issues…' : 'No queued issues.'}
        </p>
      {:else}
        <ol class="queue-list">
          {#each issues as issue, i}
            <li class="queue-item" class:queue-item-active={i === 0 && (status === 'idle' || status === 'done')}>
              <div class="queue-item-top">
                <span class="queue-pos">#{i + 1}</span>
                <span class="queue-issue-number">GH-{issue.number}</span>
                {#each issue.labels as label}
                  <span class="issue-label">{label}</span>
                {/each}
              </div>
              <div class="queue-item-title">{issue.title}</div>
              {#if i === 0 && (status === 'idle' || status === 'done')}
                <button class="btn btn-sm queue-start-btn" on:click={() => startFromIssue(issue)} disabled={submitting}>
                  {submitting ? 'Starting…' : '▶ Start now'}
                </button>
              {/if}
            </li>
          {/each}
        </ol>
      {/if}
    </section>
  </div>
</div>

<style>
  h1 { font-size: 1.8rem; margin-bottom: 1.5rem; }
  h2 { font-size: 1.1rem; margin-bottom: 0.75rem; color: #8b949e; }

  /* Two-column dashboard layout */
  .dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 1.5rem;
    align-items: start;
  }
  @media (max-width: 750px) {
    .dashboard-grid { grid-template-columns: 1fr; }
  }

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
    flex-wrap: wrap;
  }
  .label { color: #8b949e; font-size: 0.9rem; min-width: 130px; }

  .badge {
    padding: 0.2em 0.65em;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
  }
  .status-idle    { background: #21262d; color: #8b949e; }
  .status-active  { background: #1f6feb33; color: #58a6ff; }
  .status-halted  { background: #da3633; color: #fff; }

  .new-task { margin-bottom: 1.5rem; }
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
    cursor: pointer;
    transition: background 0.15s;
    text-decoration: none;
  }
  button:hover:not(:disabled), .btn:hover { background: #2ea043; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: #21262d; border: 1px solid #30363d; color: #e6edf3; }
  .btn-secondary:hover { background: #30363d; }
  .btn-sm { padding: 0.3rem 0.75rem; font-size: 0.85rem; white-space: nowrap; }

  .action-prompt, .halted-alert { margin-bottom: 1.5rem; }
  .halted-alert {
    background: #da363322;
    border: 1px solid #da3633;
    border-radius: 8px;
    padding: 1rem 1.25rem;
  }
  .halted-actions { margin-top: 0.75rem; display: flex; gap: 0.75rem; }

  .error { color: #f85149; font-size: 0.9rem; }
  .muted { color: #8b949e; font-size: 0.85rem; }

  .schedule-time { color: #e6edf3; font-size: 0.9rem; }
  .card-links { margin-top: 0.25rem; gap: 1.25rem; }
  .text-link { color: #58a6ff; font-size: 0.85rem; }
  .text-link:hover { text-decoration: underline; }

  .issue-label {
    background: #1f6feb33;
    color: #58a6ff;
    border-radius: 12px;
    font-size: 0.72rem;
    padding: 0.1em 0.5em;
  }

  /* Usage table */
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

  /* Task queue card */
  .queue-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem 1.1rem;
    position: sticky;
    top: 1rem;
  }
  .queue-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.1rem;
  }
  .queue-header h2 { margin-bottom: 0; }
  .queue-sub {
    color: #6e7681;
    font-size: 0.78rem;
    margin: 0 0 0.9rem 0;
  }
  .queue-empty { margin: 0; }

  .queue-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .queue-item {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 0.6rem 0.75rem;
  }
  .queue-item-active {
    border-color: #1f6feb;
    background: #1f6feb0d;
  }
  .queue-item-top {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.3rem;
    flex-wrap: wrap;
  }
  .queue-pos {
    font-size: 0.75rem;
    font-weight: 700;
    color: #8b949e;
  }
  .queue-issue-number {
    font-size: 0.75rem;
    color: #58a6ff;
  }
  .queue-item-title {
    font-size: 0.85rem;
    color: #e6edf3;
    line-height: 1.3;
    word-break: break-word;
    margin-bottom: 0.4rem;
  }
  .queue-start-btn {
    padding: 0.25rem 0.65rem;
    font-size: 0.8rem;
  }
</style>
