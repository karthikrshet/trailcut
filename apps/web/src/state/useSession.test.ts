import { describe, expect, it } from 'vitest';

import { sampleSession } from '../test/render';
import { reducer, type SessionState } from './useSession';

const idle: SessionState = { status: 'idle' };

describe('session reducer', () => {
  it('starts loading at the reading step', () => {
    expect(reducer(idle, { type: 'start', kind: 'sample' })).toEqual({ status: 'loading', step: 'reading', kind: 'sample' });
  });

  it('advances steps only while loading', () => {
    const loading = reducer(idle, { type: 'start', kind: 'upload' });
    expect(reducer(loading, { type: 'step', step: 'planning' })).toMatchObject({ step: 'planning' });
    expect(reducer(idle, { type: 'step', step: 'planning' })).toBe(idle);
  });

  it('loads data', () => {
    const data = sampleSession();
    expect(reducer(idle, { type: 'loaded', data })).toEqual({ status: 'ready', data, updating: false, updateError: null });
  });

  it('records failures with code and message', () => {
    expect(reducer(idle, { type: 'failed', code: 'not_a_pdf', message: 'm' })).toEqual({
      status: 'error',
      code: 'not_a_pdf',
      message: 'm',
    });
  });

  it('tracks updates and update errors without losing data', () => {
    const ready = reducer(idle, { type: 'loaded', data: sampleSession() });
    const updating = reducer(ready, { type: 'updating' });
    expect(updating).toMatchObject({ status: 'ready', updating: true });
    const failed = reducer(updating, { type: 'update_failed', message: 'nope' });
    expect(failed).toMatchObject({ status: 'ready', updating: false, updateError: 'nope' });
    expect(reducer(idle, { type: 'updating' })).toBe(idle);
    expect(reducer(idle, { type: 'update_failed', message: 'x' })).toBe(idle);
  });

  it('resets to idle', () => {
    expect(reducer(reducer(idle, { type: 'loaded', data: sampleSession() }), { type: 'reset' })).toEqual(idle);
  });
});
