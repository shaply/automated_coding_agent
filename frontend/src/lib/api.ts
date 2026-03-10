/**
 * Typed API client for the AutoDev FastAPI backend.
 * Reads VITE_API_URL and VITE_API_TOKEN from the environment.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const TOKEN = import.meta.env.VITE_API_TOKEN ?? '';

export interface Task {
  task_id: string;
  status: string;
  description: string;
  plan: string[];
  current_step: number;
  branch_name: string;
  pr_url: string;
  halt_reason: string;
}

export interface UsageEntry {
  provider: string;
  tokens_used: number;
  date: string;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${TOKEN}`,
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// --- Tasks ---

export const createTask = (description: string) =>
  request<{ task_id: string; status: string }>('/tasks', {
    method: 'POST',
    body: JSON.stringify({ description }),
  });

export const listTasks = () => request<Task[]>('/tasks');

export const getTask = (id: string) => request<Task>(`/tasks/${id}`);

export const getPlan = (id: string) => request<{ plan: string[] }>(`/tasks/${id}/plan`);

export const addPlanComment = (id: string, comment: string) =>
  request<{ ok: boolean }>(`/tasks/${id}/plan/comment`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });

export const approvePlan = (id: string) =>
  request<{ ok: boolean }>(`/tasks/${id}/plan/approve`, { method: 'POST' });

export const injectComment = (id: string, comment: string) =>
  request<{ ok: boolean }>(`/tasks/${id}/comment`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });

export const getDiff = (id: string) => request<{ diff: string }>(`/tasks/${id}/diff`);

export const approveDiff = (id: string) =>
  request<{ ok: boolean }>(`/tasks/${id}/diff/approve`, { method: 'POST' });

export const rejectDiff = (id: string) =>
  request<{ ok: boolean }>(`/tasks/${id}/diff/reject`, { method: 'POST' });

// --- Status + Usage ---

export const getStatus = () =>
  request<{ status: string; task_id: string }>('/status');

export const getUsage = () =>
  request<{ usage: UsageEntry[] }>('/usage');

// --- SSE log stream ---

export function openLogStream(taskId: string, onMessage: (msg: string) => void): EventSource {
  const es = new EventSource(`${BASE_URL}/tasks/${taskId}/stream`, {
    // EventSource doesn't support custom headers natively;
    // the backend should allow the token via a query param for SSE, or use a cookie.
    // For Phase 4+, consider a cookie-based auth or proxy approach.
  } as EventSourceInit);
  es.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data.message);
  };
  return es;
}
