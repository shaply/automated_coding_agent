<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { getPlan, addPlanComment, approvePlan, getTask, type Task } from '$lib/api';

  const id = $page.params.id;

  let task: Task | null = null;
  let plan: string[] = [];
  let comment = '';
  let error = '';
  let approving = false;
  let commenting = false;

  onMount(async () => {
    try {
      task = await getTask(id);
      const p = await getPlan(id);
      plan = p.plan;
    } catch (e: any) {
      error = e.message;
    }
  });

  async function submitComment() {
    if (!comment.trim()) return;
    commenting = true;
    error = '';
    try {
      await addPlanComment(id, comment.trim());
      comment = '';
      const p = await getPlan(id);
      plan = p.plan;
    } catch (e: any) {
      error = e.message;
    } finally {
      commenting = false;
    }
  }

  async function approve() {
    approving = true;
    error = '';
    try {
      await approvePlan(id);
      window.location.href = `/log/${id}`;
    } catch (e: any) {
      error = e.message;
      approving = false;
    }
  }
</script>

<h1>Plan Review</h1>
{#if task}
  <p class="task-desc">{task.description}</p>
{/if}

{#if error}
  <p class="error">{error}</p>
{/if}

{#if plan.length > 0}
  <ol class="plan-list">
    {#each plan as step}
      <li>{step}</li>
    {/each}
  </ol>
{:else}
  <p class="muted">Loading plan…</p>
{/if}

<div class="comment-box">
  <h2>Add a Comment</h2>
  <textarea
    bind:value={comment}
    placeholder="Suggest changes to the plan…"
    rows="3"
  ></textarea>
  <button on:click={submitComment} disabled={commenting || !comment.trim()}>
    {commenting ? 'Sending…' : 'Submit Comment'}
  </button>
</div>

<div class="approve-row">
  <button class="btn-approve" on:click={approve} disabled={approving}>
    {approving ? 'Starting implementation…' : 'Approve Plan & Start Coding'}
  </button>
</div>

<style>
  h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
  .task-desc { color: #8b949e; margin-bottom: 1.5rem; }
  .error { color: #f85149; }
  .muted { color: #6e7681; }

  .plan-list {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem 1rem 1rem 2rem;
    margin-bottom: 1.5rem;
    line-height: 2;
  }
  .plan-list li { color: #e6edf3; }

  .comment-box {
    margin-bottom: 1.5rem;
  }
  .comment-box h2 { font-size: 1rem; color: #8b949e; margin-bottom: 0.5rem; }
  textarea {
    width: 100%;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e6edf3;
    padding: 0.75rem;
    font-size: 0.9rem;
    resize: vertical;
    margin-bottom: 0.5rem;
  }
  button {
    background: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 0.45rem 1rem;
    font-size: 0.9rem;
    cursor: pointer;
  }
  button:hover:not(:disabled) { background: #30363d; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }

  .approve-row { display: flex; gap: 1rem; }
  .btn-approve {
    background: #238636;
    border-color: #238636;
    font-weight: 600;
    font-size: 1rem;
    padding: 0.6rem 1.5rem;
    color: #fff;
  }
  .btn-approve:hover:not(:disabled) { background: #2ea043; }
</style>
