/** Error raised for non-2xx responses; `code` comes from the API's `{detail: {code, message}}`. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE'
  body?: unknown
  /** Identifies the caller via the X-User-Id header (no authentication in this demo). */
  userId?: number | null
  signal?: AbortSignal
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, userId, signal } = options
  const headers: Record<string, string> = {}
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (userId !== undefined && userId !== null) {
    headers['X-User-Id'] = String(userId)
  }
  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    throw await toApiError(response, `${method} ${path} failed with ${response.status}`)
  }
  return (await response.json()) as T
}

async function toApiError(response: Response, fallback: string): Promise<ApiError> {
  let code = 'http_error'
  let message = fallback
  try {
    const data = (await response.json()) as { detail?: unknown }
    const detail = data.detail
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const typed = detail as { code?: string; message?: string }
      code = typed.code ?? code
      message = typed.message ?? message
    } else if (typeof detail === 'string') {
      message = detail
    }
  } catch {
    // body was not JSON; keep the fallback message
  }
  return new ApiError(response.status, code, message)
}
