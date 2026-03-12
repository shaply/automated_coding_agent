<script lang="ts">
  import { onMount } from 'svelte';
  import { getConfig, saveConfig } from '$lib/api';

  let yamlText = '';
  let loading = true;
  let saving = false;
  let error = '';
  let successMsg = '';

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await getConfig();
      yamlText = res.yaml_text;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function save() {
    saving = true;
    error = '';
    successMsg = '';
    try {
      const res = await saveConfig(yamlText);
      successMsg = res.message;
    } catch (e: any) {
      error = e.message;
    } finally {
      saving = false;
    }
  }

  onMount(load);
</script>

<div class="header">
  <div>
    <h1>Config Editor</h1>
    <p class="subtitle">Editing <code>config.yaml</code> — restart the container to apply changes.</p>
  </div>
  <div class="actions">
    <button on:click={load} disabled={loading || saving}>↻ Reload</button>
    <button class="btn-save" on:click={save} disabled={loading || saving}>
      {saving ? 'Saving…' : '✓ Save'}
    </button>
  </div>
</div>

{#if error}
  <div class="banner banner-error">{error}</div>
{/if}
{#if successMsg}
  <div class="banner banner-success">{successMsg}</div>
{/if}

{#if loading}
  <p class="muted">Loading…</p>
{:else}
  <textarea
    class="yaml-editor"
    bind:value={yamlText}
    spellcheck="false"
    autocomplete="off"
    autocorrect="off"
    autocapitalize="off"
  ></textarea>
{/if}

<div class="hint">
  <strong>Tip:</strong> For per-repo environment variables, add a <code>repo_envs</code> section:
  <pre class="hint-pre">repo_envs:
  my-org/my-repo:
    DATABASE_URL: "postgres://..."
    API_KEY: "..."
  my-org/another-repo:
    PORT: "3001"
    SERVICE_URL: "http://..."</pre>
  Each entry under a repo name will be injected into the agent's environment when working on that repo.
</div>

<style>
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
  }
  h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
  .subtitle { color: #8b949e; font-size: 0.85rem; margin: 0; }
  .subtitle code { background: #21262d; padding: 0.1em 0.35em; border-radius: 4px; font-size: 0.82rem; }
  .actions { display: flex; gap: 0.75rem; align-items: center; }
  button {
    background: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 0.4rem 1rem;
    font-size: 0.85rem;
    cursor: pointer;
  }
  button:hover:not(:disabled) { background: #30363d; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-save { background: #1a7f37; border-color: #2ea043; }
  .btn-save:hover:not(:disabled) { background: #2ea043; }

  .banner {
    padding: 0.6rem 1rem;
    border-radius: 6px;
    margin-bottom: 0.75rem;
    font-size: 0.875rem;
  }
  .banner-error   { background: #b6232422; border: 1px solid #b62324; color: #f85149; }
  .banner-success { background: #1a7f3722; border: 1px solid #2ea043; color: #3fb950; }

  .yaml-editor {
    width: 100%;
    height: calc(100vh - 280px);
    min-height: 400px;
    background: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 0.82rem;
    line-height: 1.6;
    resize: vertical;
    outline: none;
    box-sizing: border-box;
  }
  .yaml-editor:focus { border-color: #58a6ff; }

  .hint {
    margin-top: 1rem;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.82rem;
    color: #8b949e;
    line-height: 1.6;
  }
  .hint strong { color: #e6edf3; }
  .hint code { background: #21262d; padding: 0.1em 0.35em; border-radius: 4px; }
  .hint-pre {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 0.6rem 0.85rem;
    margin: 0.5rem 0 0.25rem;
    font-size: 0.78rem;
    color: #e6edf3;
    overflow-x: auto;
  }

  .muted { color: #8b949e; }
</style>
