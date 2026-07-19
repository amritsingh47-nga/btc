import { useEffect, useRef, useState } from 'react'

export async function apiGet<T = any>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function apiSend<T = any>(
  url: string,
  method: 'POST' | 'PATCH' | 'DELETE',
  body?: unknown
): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text.slice(0, 200)}`)
  }
  return res.json()
}

/** Poll a JSON endpoint every `intervalMs`; keeps last good value on errors. */
export function usePoll<T = any>(url: string | null, intervalMs = 10000) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!url) return
    let cancelled = false
    const tick = async () => {
      try {
        const value = await apiGet<T>(url)
        if (!cancelled) {
          setData(value)
          setError(null)
        }
      } catch (e: any) {
        if (!cancelled) setError(String(e?.message ?? e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    tick()
    timer.current = window.setInterval(tick, intervalMs)
    return () => {
      cancelled = true
      if (timer.current) window.clearInterval(timer.current)
    }
  }, [url, intervalMs])

  return { data, error, loading }
}

export function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function pctClass(n: number | null | undefined): string {
  if (n === null || n === undefined) return 'text-zinc-400'
  return n >= 0 ? 'text-emerald-400' : 'text-red-400'
}
