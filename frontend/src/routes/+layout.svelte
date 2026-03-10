<script lang="ts">
  import { page } from '$app/stores';
</script>

<nav>
  <a href="/" class:active={$page.url.pathname === '/'}>Dashboard</a>
  <a href="/history" class:active={$page.url.pathname === '/history'}>History</a>
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
    gap: 1.5rem;
    padding: 0.75rem 1.5rem;
    background: #161b22;
    border-bottom: 1px solid #30363d;
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

  main {
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1.5rem;
  }
</style>
