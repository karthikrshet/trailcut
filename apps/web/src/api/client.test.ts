import { describe, expect, it, vi } from 'vitest';

import { ApiError, createClient } from './client';

function respond(status: number, body?: unknown, json = true): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: json ? () => Promise.resolve(body) : () => Promise.reject(new Error('no json')),
  } as Response;
}

describe('api client', () => {
  it('creates a sample session', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(201, { session_id: 'abc' }));
    const client = createClient(fetchMock, '/api');
    await expect(client.sample()).resolves.toEqual({ session_id: 'abc' });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/sessions/sample', { method: 'POST' });
  });

  it('uploads as multipart with the password', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(201, { session_id: 'x' }));
    await createClient(fetchMock, '').upload(new File(['%PDF-'], 'cas.pdf'), 'PW');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/v1/sessions/upload');
    const form = init.body as FormData;
    expect(form.get('password')).toBe('PW');
    expect((form.get('file') as File).name).toBe('cas.pdf');
  });

  it('sends assumption updates as JSON PATCH', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(200, {}));
    await createClient(fetchMock, '').updateAssumptions('id/with space', { slab_rate: '0.3' });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/v1/sessions/id%2Fwith%20space/assumptions');
    expect(init.method).toBe('PATCH');
    expect(init.body).toBe('{"slab_rate":"0.3"}');
  });

  it('handles 204 on delete', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(204));
    await expect(createClient(fetchMock, '').remove('abc')).resolves.toBeUndefined();
  });

  it('maps API errors to ApiError with code and message', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(respond(422, { error: { code: 'wrong_password', message: "That password didn't open the PDF." } }));
    const err = await createClient(fetchMock, '').get('abc').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 422, code: 'wrong_password', message: "That password didn't open the PDF." });
  });

  it('falls back to a generic message for non-JSON errors', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(502, undefined, false));
    await expect(createClient(fetchMock, '').get('abc')).rejects.toMatchObject({ code: 'http_error', status: 502 });
  });

  it('reports network failures plainly', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(createClient(fetchMock, '').sample()).rejects.toMatchObject({
      code: 'network_error',
      message: "We couldn't reach TrailCut. Check your connection and try again.",
    });
  });
});
