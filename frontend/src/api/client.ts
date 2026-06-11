/**
 * Core API client — Phase 2A Slice 1.
 *
 * Typed wrapper around native `fetch`. No axios, no XMLHttpRequest.
 * Supports both production Bearer-token auth and dev bypass mode (X-User-Role).
 */

import { ApiError } from './types';

export interface AuthHeaders {
  /** Production Entra JWT */
  authorization?: string;
  /** Dev bypass role header */
  'x-user-role'?: string;
  /** Dev bypass user identity header */
  'x-user-id'?: string;
}

export interface ClientOptions {
  baseUrl?: string;
  getAuthHeaders: () => AuthHeaders | Promise<AuthHeaders>;
}

function getBaseUrl(): string {
  const env = import.meta.env.VITE_API_BASE_URL;
  return typeof env === 'string' ? env.replace(/\/$/, '') : '';
}

export class ApiClient {
  private baseUrl: string;
  private getAuthHeaders: ClientOptions['getAuthHeaders'];

  constructor(options?: Partial<ClientOptions>) {
    this.baseUrl = options?.baseUrl ?? getBaseUrl();
    this.getAuthHeaders = options?.getAuthHeaders ?? (() => ({}));
  }

  private async buildHeaders(
    init?: RequestInit,
  ): Promise<Record<string, string>> {
    const explicitHeaders = new Headers(init?.headers);
    const auth = explicitHeaders.has('authorization')
      ? {}
      : await this.getAuthHeaders();
    const headers: Record<string, string> = {
      Accept: 'application/json',
      ...Object.fromEntries(
        Object.entries(auth).filter(([, v]) => v !== undefined),
      ),
    };

    if (init?.body && typeof init.body === 'string') {
      headers['Content-Type'] = 'application/json';
    }

    // Merge any user-provided headers (they take precedence)
    if (init?.headers) {
      const userHeaders =
        init.headers instanceof Headers
          ? Object.fromEntries(init.headers.entries())
          : (init.headers as Record<string, string>);
      Object.assign(headers, userHeaders);
    }

    return headers;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers = await this.buildHeaders(init);

    let response: Response;
    try {
      response = await fetch(url, { ...init, headers });
    } catch (networkErr) {
      const message =
        networkErr instanceof Error ? networkErr.message : 'Network error';
      throw new ApiError(0, message);
    }

    if (!response.ok) {
      let body: unknown = null;
      try {
        body = await response.json();
      } catch {
        // body stays null if not JSON
      }
      const detail =
        (body && typeof body === 'object' && 'detail' in body
          ? String(body.detail)
          : null) ||
        response.statusText ||
        `HTTP ${response.status}`;
      throw new ApiError(response.status, detail, body);
    }

    // 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    try {
      return (await response.json()) as T;
    } catch {
      return undefined as T;
    }
  }

  get<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...init, method: 'GET' });
  }

  post<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...init,
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /**
   * POST multipart form data (e.g. `POST /upload`). The browser sets the
   * multipart Content-Type boundary, so no Content-Type header is forced.
   */
  postForm<T>(path: string, body: FormData, init?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...init, method: 'POST', body });
  }

  put<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...init,
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }

  delete<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...init, method: 'DELETE' });
  }

  /**
   * Download a file as a Blob. Used by Export Panel for report artifacts.
   * Keeps `fetch` inside this module per Phase 2A network policy.
   */
  async download(path: string): Promise<Blob> {
    const url = `${this.baseUrl}${path}`;
    const headers = await this.buildHeaders({ method: 'GET' });

    let response: Response;
    try {
      response = await fetch(url, { method: 'GET', headers });
    } catch (networkErr) {
      const message =
        networkErr instanceof Error ? networkErr.message : 'Network error';
      throw new ApiError(0, message);
    }

    if (!response.ok) {
      const detail = response.statusText || `HTTP ${response.status}`;
      throw new ApiError(response.status, detail);
    }
    return response.blob();
  }
}

/** Default singleton client with no auth — replace via `useApi()` in React. */
export const api = new ApiClient();
