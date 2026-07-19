import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  type IChartApi,
  type CandlestickData,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts'

export type Candle = {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
}

export type Marker = {
  time: string // "YYYY-MM-DD HH:MM:SS" from the backend
  action: 'long' | 'short'
  confidence?: number
  would_veto?: boolean
}

export function CandleChart({
  candles,
  markers = [],
  height = 380,
}: {
  candles: Candle[]
  markers?: Marker[]
  height?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = createChart(ref.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#a1a1aa',
      },
      grid: {
        vertLines: { color: '#27272a' },
        horzLines: { color: '#27272a' },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      rightPriceScale: { borderColor: '#3f3f46' },
      crosshair: { mode: 0 },
    })
    chartRef.current = chart
    const series = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    })

    const data: CandlestickData[] = candles.map((c) => ({
      time: (c.timestamp / 1000) as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    series.setData(data)

    if (markers.length && data.length) {
      const first = data[0].time as number
      const last = data[data.length - 1].time as number
      const seriesMarkers: SeriesMarker<Time>[] = markers
        .map((m) => {
          const t = Math.floor(new Date(m.time.replace(' ', 'T')).getTime() / 1000)
          return { ...m, t }
        })
        .filter((m) => m.t >= first && m.t <= last)
        .map((m) => ({
          time: m.t as Time,
          position: m.action === 'long' ? 'belowBar' : 'aboveBar',
          color: m.would_veto ? '#f59e0b' : m.action === 'long' ? '#10b981' : '#ef4444',
          shape: m.action === 'long' ? 'arrowUp' : 'arrowDown',
          text: `${m.would_veto ? 'VETO ' : ''}${m.action.toUpperCase()}${
            m.confidence ? ` ${Math.round(m.confidence)}%` : ''
          }`,
        }))
      series.setMarkers(seriesMarkers)
    }

    chart.timeScale().fitContent()

    const onResize = () => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth })
    }
    onResize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.remove()
      chartRef.current = null
    }
  }, [candles, markers, height])

  return <div ref={ref} className="w-full" />
}

export function Sparkline({
  values,
  width = 120,
  height = 32,
}: {
  values: number[]
  width?: number
  height?: number
}) {
  if (!values || values.length < 2) return <span className="text-zinc-600">—</span>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const points = values
    .map(
      (v, i) =>
        `${((i / (values.length - 1)) * width).toFixed(1)},${(
          height -
          ((v - min) / range) * height
        ).toFixed(1)}`
    )
    .join(' ')
  const up = values[values.length - 1] >= values[0]
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={up ? '#10b981' : '#ef4444'}
        strokeWidth="1.5"
      />
    </svg>
  )
}
