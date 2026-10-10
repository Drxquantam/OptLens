import type { Health, HistoryItem, JobInfo, Preset } from './types';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError('Cannot reach the OptLens API. Is the backend running on port 8000?', 0);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join('; ');
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  analyze: (source: string, stdin: string, presetId: string | null) =>
    request<{ job_id: string; status: string; queue_position: number | null }>('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ source, stdin, preset_id: presetId }),
    }),
  job: (id: string) => request<JobInfo>(`/api/jobs/${id}`),
  presets: () => request<Preset[]>('/api/presets'),
  history: () => request<HistoryItem[]>('/api/history?limit=15'),
  health: () => request<Health>('/api/health'),
};
