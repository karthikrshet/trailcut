import type {
  ApiErrorBody,
  AssumptionsUpdate,
  ChatResponse,
  ChatTurn,
  EstimateRequest,
  EstimateResponse,
  SessionResponse,
} from './types';

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api';

/** An API failure with a stable code and a message that is safe to show. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

const NETWORK_MESSAGE = "We couldn't reach TrailCut. Check your connection and try again.";

type Fetch = typeof fetch;

export function createClient(fetchImpl: Fetch = (input, init) => fetch(input, init), base = BASE) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await fetchImpl(`${base}${path}`, init);
    } catch {
      throw new ApiError(0, 'network_error', NETWORK_MESSAGE);
    }
    if (response.status === 204) return undefined as T;
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    if (!response.ok) {
      const err = (body as ApiErrorBody | undefined)?.error;
      throw new ApiError(
        response.status,
        err?.code ?? 'http_error',
        err?.message ?? 'Something went wrong on our side. Please try again.',
      );
    }
    return body as T;
  }

  return {
    estimate: (body: EstimateRequest) =>
      request<EstimateResponse>('/v1/estimate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    sample: () => request<SessionResponse>('/v1/sessions/sample', { method: 'POST' }),
    upload: (file: File, password: string) => {
      const form = new FormData();
      form.append('file', file);
      form.append('password', password);
      return request<SessionResponse>('/v1/sessions/upload', { method: 'POST', body: form });
    },
    get: (id: string) => request<SessionResponse>(`/v1/sessions/${encodeURIComponent(id)}`),
    updateAssumptions: (id: string, update: AssumptionsUpdate) =>
      request<SessionResponse>(`/v1/sessions/${encodeURIComponent(id)}/assumptions`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update),
      }),
    chat: (id: string, message: string, history: ChatTurn[]) =>
      request<ChatResponse>(`/v1/sessions/${encodeURIComponent(id)}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history }),
      }),
    remove: (id: string) =>
      request<undefined>(`/v1/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  };
}

export type Client = ReturnType<typeof createClient>;
