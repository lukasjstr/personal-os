import { API_BASE_URL, API_TIMEOUT_MS } from '../config/api';
import { getToken } from './storage';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() =>
    clearTimeout(timer),
  );
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (authenticated) {
    const token = await getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  let response: Response;
  try {
    response = await fetchWithTimeout(
      `${API_BASE_URL}${path}`,
      { ...options, headers },
      API_TIMEOUT_MS,
    );
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError(0, 'Request timed out');
    }
    throw new ApiError(0, 'Network error — check your connection');
  }

  if (!response.ok) {
    const body = await response.text().catch(() => response.statusText);
    throw new ApiError(response.status, body || `HTTP ${response.status}`);
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : {}) as T;
}

/** Validate a token against the backend. Returns true if accepted. */
export async function validateToken(token: string): Promise<boolean> {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/auth/validate`,
      {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      },
      API_TIMEOUT_MS,
    );
    return response.ok;
  } catch {
    return false;
  }
}
