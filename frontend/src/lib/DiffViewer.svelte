<script lang="ts">
  import { onMount } from 'svelte';

  export let diff: string = '';

  let highlighted = '';

  onMount(async () => {
    const hljs = (await import('highlight.js')).default;
    highlighted = hljs.highlight(diff || '(no changes)', { language: 'diff' }).value;
  });
</script>

<svelte:head>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css" />
</svelte:head>

<div class="diff-viewer">
  {#if highlighted}
    <!-- eslint-disable-next-line svelte/no-at-html-tags -->
    <pre><code class="hljs language-diff">{@html highlighted}</code></pre>
  {:else}
    <pre>{diff || '(no changes)'}</pre>
  {/if}
</div>

<style>
  .diff-viewer {
    background: #0d1117;
    border-radius: 6px;
    overflow: auto;
    max-height: 600px;
  }
  pre {
    margin: 0;
    padding: 1rem;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.85rem;
    line-height: 1.5;
  }
</style>
