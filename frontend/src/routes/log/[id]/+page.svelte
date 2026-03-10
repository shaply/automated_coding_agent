<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import LogStream from '$lib/LogStream.svelte';
  import { getTask, injectComment, type Task } from '$lib/api';

  const id = $page.params.id;

  let task: Task | null = null;
  let comment = '';
  let sending = false;
  let error = '';

  onMount(async () => {
    try {
      task = await getTask(id);
    } catch (e: any) {
      error = e.message;
    }

    // Poll for status change to redirect to diff review when done
    const poll = setInterval(async () => {
      try {
        const t = await getTask(id);
        task = t;
        if (t.status === 'awaiting_diff_review') {
          clearInterval(poll);
          window.location.href = `/diff/${id}`;
        } else if (t.status.startsWith('halted') || t.status === 'done' || t.status === 'idle') {
          clearInterval(poll);
        }
      } catch {}
    }, 3000);

    return () => clearInterval(poll);
  });

  async function sendComment() {
    if (!comment.trim()) return;
    sending = true;
    error = '';
    try {
      await injectComment(id, comment.trim());
      comment = '';
    } catch (e: any) {
      error = e.message;
    } finally {
      sending = false;
    }
  }
</script>

<h1>Live Implementation Log</h1>

{#if task}
  <p class="task-desc">
    Step {task.current_step + 1} &middot; Status: <strong>{task.status}</strong>
  </p>
{/if}

{#if error}
  <p class="error">{error}</p>
{/if}

<LogStream taskId={id} />

<div class="comment-box">
  <h2>Inject a Comment</h2>
  <p class="hint">The agent will immediately adjust its approach.</p>
  <textarea
    bind:value={comment}
    placeholder="E.g. 'Use async/await instead of callbacks'"
    rows="2"
  ></textarea>
  <button on:click={sendComment} disabled={sending || !comment.trim()}>
    {sending ? 'Sending…' : 'Send to Agent'}
  </button>
</div>

<style>
  h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
  .task-desc { color: #8b949e; margin-bottom: 1rem; }
  .error { color: #f85149; }

  .comment-box { margin-top: 1.5rem; }
  .comment-box h2 { font-size: 1rem; color: #8b949e; margin-bottom: 0.25rem; }
  .hint { font-size: 0.85rem; color: #6e7681; margin-bottom: 0.5rem; }
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
</style>
