import { useCallback, useReducer, useRef } from 'react';

import { ApiError, type Client } from '../api/client';
import type { AssumptionsUpdate, SessionResponse } from '../api/types';

export type Step = 'reading' | 'pricing' | 'planning';

export type SessionState =
  | { status: 'idle' }
  | { status: 'loading'; step: Step; kind: 'sample' | 'upload' }
  | { status: 'ready'; data: SessionResponse; updating: boolean; updateError: string | null }
  | { status: 'error'; code: string; message: string };

type Event =
  | { type: 'start'; kind: 'sample' | 'upload' }
  | { type: 'step'; step: Step }
  | { type: 'loaded'; data: SessionResponse }
  | { type: 'failed'; code: string; message: string }
  | { type: 'updating' }
  | { type: 'update_failed'; message: string }
  | { type: 'reset' };

export function reducer(state: SessionState, event: Event): SessionState {
  switch (event.type) {
    case 'start':
      return { status: 'loading', step: 'reading', kind: event.kind };
    case 'step':
      return state.status === 'loading' ? { ...state, step: event.step } : state;
    case 'loaded':
      return { status: 'ready', data: event.data, updating: false, updateError: null };
    case 'failed':
      return { status: 'error', code: event.code, message: event.message };
    case 'updating':
      return state.status === 'ready' ? { ...state, updating: true, updateError: null } : state;
    case 'update_failed':
      return state.status === 'ready' ? { ...state, updating: false, updateError: event.message } : state;
    case 'reset':
      return { status: 'idle' };
  }
}

function toFailure(err: unknown): { code: string; message: string } {
  if (err instanceof ApiError) return { code: err.code, message: err.message };
  return { code: 'unexpected', message: 'Something went wrong. Please try again.' };
}

/** Session lifecycle: sample/upload → ready → update assumptions → delete. */
export function useSession(client: Client) {
  const [state, dispatch] = useReducer(reducer, { status: 'idle' });
  const timers = useRef<number[]>([]);

  const clearTimers = () => {
    timers.current.forEach((t) => {
      window.clearTimeout(t);
    });
    timers.current = [];
  };

  const run = useCallback(
    async (kind: 'sample' | 'upload', call: () => Promise<SessionResponse>) => {
      dispatch({ type: 'start', kind });
      // Honest progress: steps advance while the single request is in flight.
      timers.current.push(window.setTimeout(() => { dispatch({ type: 'step', step: 'pricing' }); }, 500));
      timers.current.push(window.setTimeout(() => { dispatch({ type: 'step', step: 'planning' }); }, 1100));
      try {
        const data = await call();
        dispatch({ type: 'loaded', data });
      } catch (err) {
        dispatch({ type: 'failed', ...toFailure(err) });
      } finally {
        clearTimers();
      }
    },
    [],
  );

  const startSample = useCallback(() => run('sample', () => client.sample()), [client, run]);
  const upload = useCallback(
    (file: File, password: string) => run('upload', () => client.upload(file, password)),
    [client, run],
  );

  const update = useCallback(
    async (change: AssumptionsUpdate) => {
      if (state.status !== 'ready') return;
      dispatch({ type: 'updating' });
      try {
        dispatch({ type: 'loaded', data: await client.updateAssumptions(state.data.session_id, change) });
      } catch (err) {
        const f = toFailure(err);
        if (f.code === 'session_expired') dispatch({ type: 'failed', ...f });
        else dispatch({ type: 'update_failed', message: f.message });
      }
    },
    [client, state],
  );

  const deleteData = useCallback(async () => {
    if (state.status === 'ready') {
      try {
        await client.remove(state.data.session_id);
      } catch {
        // Already gone or unreachable: it expires on its own within 30 minutes.
      }
    }
    dispatch({ type: 'reset' });
  }, [client, state]);

  const reset = useCallback(() => { dispatch({ type: 'reset' }); }, []);

  return { state, startSample, upload, update, deleteData, reset };
}
