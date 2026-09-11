import { useCallback, useState } from 'react'

export type ToastKind = 'info' | 'success' | 'warning' | 'error'

export interface ToastInput {
  kind: ToastKind
  text: string
}

export interface Toast extends ToastInput {
  id: number
}

const LIFETIME_MS: Record<ToastKind, number> = {
  info: 5000,
  success: 5000,
  warning: 10_000,
  error: 8000,
}

let nextId = 1

/** Transient notifications; each one disappears on its own after a kind-specific lifetime. */
export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback(
    (input: ToastInput) => {
      const id = nextId++
      setToasts((current) => [...current, { id, ...input }])
      window.setTimeout(() => dismiss(id), LIFETIME_MS[input.kind])
    },
    [dismiss],
  )

  return { toasts, notify, dismiss }
}
