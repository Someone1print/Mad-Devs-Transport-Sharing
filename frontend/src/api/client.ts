/** Error raised for non-2xx responses; `code` comes from the API's `{detail: {code, message}}`. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  /** The rest of the server's `detail` object (e.g. `problem` for invalid_email). */
  readonly detail: Record<string, unknown>

  constructor(status: number, code: string, message: string, detail: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

/** Fired on the window when the server answers 401: the session is gone, show the sign-in. */
export const SESSION_LOST_EVENT = 'transport-sharing:session-lost'

/**
 * The browser identifies itself with the HttpOnly session cookie the server set at sign-in;
 * fetch sends it on every same-origin request, so nothing about the user travels in code.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options
  const headers: Record<string, string> = {}
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
    credentials: 'same-origin',
  })
  if (!response.ok) {
    const error = await toApiError(response, `${method} ${path} failed with ${response.status}`)
    if (error.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event(SESSION_LOST_EVENT))
    }
    throw error
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function toApiError(response: Response, fallback: string): Promise<ApiError> {
  let code = 'http_error'
  let message = fallback
  let extra: Record<string, unknown> = {}
  try {
    const data = (await response.json()) as { detail?: unknown }
    const detail = data.detail
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const typed = detail as { code?: string; message?: string }
      code = typed.code ?? code
      message = typed.message ?? message
      extra = detail as Record<string, unknown>
    } else if (typeof detail === 'string') {
      message = detail
    }
  } catch {
    // body was not JSON; keep the fallback message
  }
  return new ApiError(response.status, code, message, extra)
}
