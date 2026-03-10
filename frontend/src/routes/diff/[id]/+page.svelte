<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import DiffViewer from '$lib/DiffViewer.svelte';
  import { getDiff, approveDiff, rejectDiff, getTask, type Task } from '$lib/api';

  const id = $page.params.id;

  let task: Task | null = null;
  let diff = '';
  let error = '';
  let approving = false;
  let rejecting = false;

  onMount(async () => {
    try {
      [task, { diff }] = await Promise.all([getTask(id), getDiff(id)]);
    } catch (e: any) {
      error = e.message;
    }
  });

  async function approve() {
    approving = true;
    error = '';
    try {
      await approveDiff(id);
      window.location.href = '/';
    } catch (e: any) {
      error = e.message;
      approving = false;
    }
  }

  async function reject() {
    if (!confirm('Reject and discard all changes? This cannot be undone.')) return;
    rejecting = true;
    error = '';
    try {
      await rejectDiff(id);
      window.location.href = '/';
    } catch (e: any) {
      error = e.message;
      rejecting = false;
    }
  }
</script>

<h1>Diff Review</h1>

{#if task}
  <p class="task-desc">{task.description}</p>
  {#if task.status === 'halted:credits_exhausted'}
    <div class="partial-warning">
      Partial work — credits exhausted. Review what was completed and decide below.
    </div>
  {/if}
{/if}

{#if error}
  <p class="error">{error}</p>
{/if}

<DiffViewer {diff} />

<div class="actions">
  <button class="btn-approve" on:click={approve} disabled={approving || rejecting}>
    {approving ? 'Pushing branch…' : 'Approve & Push Branch'}
  </button>
  <button class="btn-reject" on:click={reject} disabled={approving || rejecting}>
    {rejecting ? 'Discarding…' : 'Reject & Discard'}
  </button>
</div>

<style>
  h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
  .task-desc { color: #8b949e; margin-bottom: 1rem; }
  .error { color: #f85149; }
  .partial-warning {
    background: #b45309;
    color: #fff;
    border-radius: 6px;
    padding: 0.5rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.5rem;
  }
  button {
    border-radius: 6px;
    padding: 0.55rem 1.25rem;
    font-size: 0.95rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: background 0.15s;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-approve { background: #238636; color: #fff; }
  .btn-approve:hover:not(:disabled) { background: #2ea043; }
  .btn-reject { background: #da3633; color: #fff; }
  .btn-reject:hover:not(:disabled) { background: #b91c1c; }
</style>
