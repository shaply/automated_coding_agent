/**
 * Typed API client for the AutoDev FastAPI backend.
 * Reads VITE_API_URL and VITE_API_TOKEN from the environment.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8094';
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
  step_failure_info: { step?: number; description?: string; output?: string } | null;
  issue_number: number | null;
}

export interface GitHubIssue {
  number: number;
  title: string;
  body: string;
  url: string;
  labels: string[];
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

export const createTask = (description: string, issue_number?: number) =>
  request<{ task_id: string; status: string }>('/tasks', {
    method: 'POST',
    body: JSON.stringify({ description, issue_number: issue_number ?? null }),
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

export const resolveStepFailure = (id: string, choice: string) =>
  request<{ ok: boolean }>(`/tasks/${id}/step-failure`, {
    method: 'POST',
    body: JSON.stringify({ choice }),
  });

// --- GitHub Issues ---

export const listIssues = () =>
  request<{ issues: GitHubIssue[] }>('/issues');

export const refreshIssues = () =>
  request<{ issues: GitHubIssue[]; message: string }>('/schedule/refresh', { method: 'POST' });

// --- Schedule ---

export interface ScheduleInfo {
  enabled: boolean;
  time: string;
  timezone: string;
  next_run: string | null;
}

export const getSchedule = () => request<ScheduleInfo>('/schedule');

// --- Status + Usage ---

export const getStatus = () =>
  request<{ status: string; task_id: string }>('/status');

export const getUsage = () =>
  request<{ usage: UsageEntry[] }>('/usage');

// --- Stats ---

export interface ProviderTotal {
  provider: string;
  total_tokens: number;
  days_active: number;
}

export interface DailyUsage {
  provider: string;
  date: string;
  tokens_used: number;
}

export interface StatsResponse {
  totals_by_provider: ProviderTotal[];
  daily_history: DailyUsage[];
  providers_config: Record<string, { daily_token_budget: number; model: string }>;
}

export const getStats = () => request<StatsResponse>('/stats');

// --- Logs ---

export const getLogs = (lines = 200) =>
  request<{ lines: string[] }>(`/logs?lines=${lines}`);

// --- Config ---

export const getConfig = () => request<{ yaml_text: string }>('/config');

export const saveConfig = (yaml_text: string) =>
  request<{ ok: boolean; message: string }>('/config', {
    method: 'POST',
    body: JSON.stringify({ yaml_text }),
  });

// --- Admin ---

export const stopAgent = () =>
  request<{ ok: boolean; message: string }>('/admin/stop', { method: 'POST' });

export const resetSession = () =>
  request<{ ok: boolean; status: string }>('/admin/reset', { method: 'POST' });

// --- SSE log stream ---

export function openLogStream(taskId: string, onMessage: (msg: string) => void): EventSource {
  // Token passed as query param — EventSource can't send Authorization headers.
  const url = `${BASE_URL}/tasks/${taskId}/stream?token=${encodeURIComponent(TOKEN)}`;
  const es = new EventSource(url);
  es.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data.message);
  };
  return es;
}
