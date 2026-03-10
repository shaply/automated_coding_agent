<script lang="ts">
  import { onMount } from 'svelte';
  import { listTasks, type Task } from '$lib/api';

  let tasks: Task[] = [];
  let error = '';

  onMount(async () => {
    try {
      tasks = await listTasks();
    } catch (e: any) {
      error = e.message;
    }
  });

  function statusBadgeClass(status: string) {
    if (status === 'done') return 'badge-done';
    if (status.startsWith('halted')) return 'badge-halted';
    if (status === 'idle') return 'badge-idle';
    return 'badge-active';
  }
</script>

<h1>Task History</h1>

{#if error}
  <p class="error">{error}</p>
{/if}

{#if tasks.length === 0}
  <p class="muted">No tasks yet.</p>
{:else}
  <ul class="task-list">
    {#each tasks as task}
      <li class="task-item">
        <div class="task-header">
          <span class="badge {statusBadgeClass(task.status)}">{task.status}</span>
          <code class="task-id">{task.task_id.slice(0, 8)}</code>
        </div>
        <p class="task-desc">{task.description || '(no description)'}</p>
        {#if task.pr_url}
          <a href={task.pr_url} target="_blank" rel="noopener">View PR →</a>
        {/if}
        {#if task.halt_reason}
          <p class="halt-reason">{task.halt_reason}</p>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }
  .error { color: #f85149; }
  .muted { color: #6e7681; }

  .task-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .task-item {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem 1.25rem;
  }
  .task-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }
  .task-id { font-size: 0.8rem; color: #6e7681; }
  .task-desc { margin: 0 0 0.5rem; color: #c9d1d9; }
  .halt-reason { font-size: 0.85rem; color: #f85149; margin: 0; }

  .badge {
    padding: 0.2em 0.65em;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
  }
  .badge-idle   { background: #21262d; color: #8b949e; }
  .badge-active { background: #1f6feb33; color: #58a6ff; }
  .badge-done   { background: #238636; color: #fff; }
  .badge-halted { background: #da3633; color: #fff; }
</style>
