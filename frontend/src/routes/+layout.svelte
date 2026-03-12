<script lang="ts">
  import { page } from '$app/stores';
  import { stopAgent } from '$lib/api';

  let stopping = false;

  async function handleStop() {
    if (!confirm('Gracefully stop the AutoDev agent? The container will exit — restart it to bring it back.')) return;
    stopping = true;
    try {
      await stopAgent();
    } catch {
      // SIGTERM causes the connection to close before a response arrives — that's expected
    }
    stopping = false;
  }
</script>

<nav>
  <div class="nav-links">
    <a href="/" class:active={$page.url.pathname === '/'}>Dashboard</a>
    <a href="/history" class:active={$page.url.pathname === '/history'}>History</a>
    <a href="/logs" class:active={$page.url.pathname === '/logs'}>Logs</a>
    <a href="/stats" class:active={$page.url.pathname === '/stats'}>Statistics</a>
    <a href="/config" class:active={$page.url.pathname === '/config'}>Config</a>
  </div>
  <button class="stop-btn" on:click={handleStop} disabled={stopping} title="Gracefully stop the agent process">
    {stopping ? '…' : '⏹ Stop'}
  </button>
</nav>

<main>
  <slot />
</main>

<style>
  :global(*, *::before, *::after) {
    box-sizing: border-box;
  }
  :global(body) {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: #0d1117;
    color: #e6edf3;
  }
  :global(a) {
    color: #58a6ff;
    text-decoration: none;
  }
  :global(button) {
    cursor: pointer;
  }

  nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.5rem;
    background: #161b22;
    border-bottom: 1px solid #30363d;
  }
  .nav-links {
    display: flex;
    gap: 1.5rem;
    align-items: center;
  }
  nav a {
    color: #8b949e;
    font-size: 0.9rem;
    font-weight: 500;
    transition: color 0.15s;
  }
  nav a:hover,
  nav a.active {
    color: #e6edf3;
  }

  .stop-btn {
    background: transparent;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 0.3rem 0.8rem;
    font-size: 0.82rem;
    transition: color 0.15s, border-color 0.15s;
  }
  .stop-btn:hover:not(:disabled) {
    color: #f85149;
    border-color: #b62324;
  }
  .stop-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  main {
    max-width: 1100px;
    margin: 2rem auto;
    padding: 0 1.5rem;
  }
</style>
