<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { openLogStream } from './api';

  export let taskId: string;

  let lines: string[] = [];
  let es: EventSource | null = null;
  let container: HTMLElement;

  onMount(() => {
    es = openLogStream(taskId, (msg) => {
      lines = [...lines, msg];
      // Auto-scroll to bottom
      setTimeout(() => {
        if (container) container.scrollTop = container.scrollHeight;
      }, 0);
    });
  });

  onDestroy(() => {
    es?.close();
  });
</script>

<div class="log-stream" bind:this={container}>
  {#each lines as line}
    <div class="log-line">{line}</div>
  {/each}
  {#if lines.length === 0}
    <div class="log-empty">Waiting for log output…</div>
  {/if}
</div>

<style>
  .log-stream {
    background: #0d1117;
    color: #c9d1d9;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.85rem;
    padding: 1rem;
    border-radius: 6px;
    height: 400px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .log-line {
    margin-bottom: 2px;
  }
  .log-empty {
    color: #6e7681;
    font-style: italic;
  }
</style>
