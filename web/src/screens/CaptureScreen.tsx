/**
 * Screen 1 — Capture
 *
 * Two modes:
 *   Camera: tap photo → POST /api/detect → overlay detections → confirm/correct
 *   Manual: blank table SVG → tap to add ball → select id → drag to position
 */

import { useRef, useState } from 'react'
import { TableView } from '../components/TableView'
import { fetchDetect } from '../api/client'
import { useSession } from '../store/session'
import type { BallState, DetectedBall } from '../types/pillars'
import { BALL_COLORS, PLACEMENT_ORDER } from '../types/pillars'

type Mode = 'menu' | 'camera' | 'manual'

/**
 * Downscale an image File to a JPEG Blob with a max dimension, using the
 * browser's native decoder (handles HEIC on iOS) and a canvas re-encode.
 * Keeps uploads small and guarantees a format OpenCV can read.
 */
async function downscaleToJpeg(file: File, maxDim: number): Promise<File> {
  const bitmap = await createImageBitmap(file).catch(() => null)
  let width: number
  let height: number
  let source: CanvasImageSource

  if (bitmap) {
    width = bitmap.width
    height = bitmap.height
    source = bitmap
  } else {
    // Fallback: decode via <img> (covers browsers without createImageBitmap HEIC support)
    const url = URL.createObjectURL(file)
    try {
      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const el = new Image()
        el.onload = () => resolve(el)
        el.onerror = () => reject(new Error('Could not decode the photo.'))
        el.src = url
      })
      width = img.naturalWidth
      height = img.naturalHeight
      source = img
    } finally {
      URL.revokeObjectURL(url)
    }
  }

  const scale = Math.min(1, maxDim / Math.max(width, height))
  const w = Math.round(width * scale)
  const h = Math.round(height * scale)

  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not available for image processing.')
  ctx.drawImage(source, 0, 0, w, h)
  if (bitmap) bitmap.close()

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', 0.85)
  )
  if (!blob) throw new Error('Could not encode the photo.')
  return new File([blob], 'table.jpg', { type: 'image/jpeg' })
}

export function CaptureScreen() {
  const { setBalls, setScreen, setError } = useSession()
  const [mode, setMode] = useState<Mode>('menu')
  const [loading, setLoading] = useState(false)
  const [detected, setDetected] = useState<DetectedBall[]>([])
  const [localBalls, setLocalBalls] = useState<BallState[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  // ---- Camera mode ----

  async function handleImageFile(file: File) {
    setLoading(true)
    setError(null)
    try {
      // Downscale + transcode to JPEG before upload. Phone photos are 12MP+
      // and often HEIC (which OpenCV can't decode); a ~1600px JPEG uploads
      // fast and the vision pipeline handles it in well under a second.
      const prepared = await downscaleToJpeg(file, 1600)
      const result = await fetchDetect(prepared)
      const balls: BallState[] = result.balls
        .filter((b) => b.id !== null)
        .map((b) => ({ id: b.id!, x_m: b.x_m, y_m: b.y_m }))
      setDetected(result.balls)
      setLocalBalls(balls)
    } catch (e) {
      setError((e as Error).message || 'Could not read the photo. Try manual placement.')
    } finally {
      setLoading(false)
    }
  }

  // ---- Manual mode ----

  // Next ball to place, in order: 8 → 9 → cue.
  const nextBallId = PLACEMENT_ORDER.find(
    (id) => !localBalls.some((b) => b.id === id)
  ) ?? null

  function handleTableTap(x_m: number, y_m: number) {
    if (!nextBallId) return  // all three placed
    setLocalBalls((prev) => [...prev, { id: nextBallId, x_m, y_m }])
  }

  function updateBall(id: string, x_m: number, y_m: number) {
    setLocalBalls((prev) =>
      prev.map((b) => (b.id === id ? { ...b, x_m, y_m } : b))
    )
  }

  function removeBall(id: string) {
    setLocalBalls((prev) => prev.filter((b) => b.id !== id))
  }

  function confirmLayout() {
    setBalls(localBalls)
    setScreen('table')
  }

  // ---- Render ----

  if (mode === 'menu') {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white px-6 gap-6">
        <div className="text-center mb-4">
          <h1 className="text-2xl font-bold tracking-widest text-[#facc15]">RŌ</h1>
          <p className="text-xs text-gray-500 mt-1 tracking-widest uppercase">Pool Sauce Engine</p>
        </div>
        <p className="text-sm text-gray-400 text-center">Set the table. Choose your method.</p>
        <button
          className="w-full max-w-xs py-4 rounded border border-[#facc15] text-[#facc15] tracking-widest text-sm font-bold hover:bg-[#facc1510] transition"
          onClick={() => { setMode('camera'); fileRef.current?.click() }}
        >
          PHOTOGRAPH THE TABLE
        </button>
        <button
          className="w-full max-w-xs py-4 rounded border border-gray-600 text-gray-300 tracking-widest text-sm hover:bg-white/5 transition"
          onClick={() => setMode('manual')}
        >
          PLACE BALLS MANUALLY
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) handleImageFile(f)
          }}
        />
      </div>
    )
  }

  if (mode === 'camera' && loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white gap-4">
        <div className="w-8 h-8 border-2 border-[#facc15] border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400 text-sm tracking-widest">READING THE TABLE</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <button
          className="text-gray-500 text-xs tracking-widest"
          onClick={() => { setMode('menu'); setLocalBalls([]); setDetected([]) }}
        >
          ← BACK
        </button>
        <span className="text-xs text-gray-600 tracking-widest uppercase">
          {mode === 'camera' ? 'Confirm Detection' : 'Place Balls'}
        </span>
        <span className="text-xs text-gray-700">{localBalls.length} balls</span>
      </div>

      {/* Table */}
      <div className="px-3">
        <TableView
          balls={localBalls}
          onBallMove={updateBall}
          onTableTap={mode === 'manual' ? handleTableTap : undefined}
        />
      </div>

      {/* Detection flags */}
      {detected.filter((b) => b.needs_confirm).length > 0 && (
        <div className="mx-4 mt-2 p-3 rounded border border-amber-600/40 bg-amber-900/10">
          <p className="text-xs text-amber-400 tracking-wide">
            {detected.filter((b) => b.needs_confirm).length} ball(s) need confirmation — drag to correct position.
          </p>
        </div>
      )}

      {/* Manual: next-ball-to-place prompt (8 → 9 → cue) */}
      {mode === 'manual' && nextBallId && (
        <div className="mx-4 mt-3 flex items-center justify-center gap-3 p-3 rounded border border-gray-700 bg-gray-900">
          <span className="text-xs text-gray-400 tracking-widest">TAP TO PLACE</span>
          <span
            className="w-9 h-9 rounded-full border flex items-center justify-center text-sm font-bold"
            style={{
              backgroundColor: (BALL_COLORS[nextBallId] ?? '#666') + '33',
              borderColor: BALL_COLORS[nextBallId] ?? '#666',
              color: nextBallId === 'cue' ? '#fff' : '#fff',
            }}
          >
            {nextBallId === 'cue' ? 'CUE' : nextBallId}
          </span>
        </div>
      )}
      {mode === 'manual' && !nextBallId && (
        <p className="text-center text-xs text-green-400 mt-3 tracking-widest">
          ALL THREE PLACED — DRAG TO ADJUST
        </p>
      )}

      {/* Ball list + remove */}
      {localBalls.length > 0 && (
        <div className="mx-4 mt-3 flex flex-wrap gap-2">
          {localBalls.map((b) => (
            <button
              key={b.id}
              onClick={() => removeBall(b.id)}
              className="px-2 py-1 rounded text-xs border opacity-70 hover:opacity-100 transition"
              style={{ borderColor: BALL_COLORS[b.id] ?? '#666', color: BALL_COLORS[b.id] ?? '#666' }}
              title={`Remove ${b.id}`}
            >
              {b.id} ×
            </button>
          ))}
        </div>
      )}

      {/* Confirm */}
      <div className="mt-auto px-4 pb-8 pt-4">
        <button
          disabled={localBalls.length < 2}
          onClick={confirmLayout}
          className="w-full py-4 rounded bg-[#facc15] text-black font-bold tracking-widest text-sm disabled:opacity-30 transition"
        >
          CONFIRM LAYOUT →
        </button>
      </div>
    </div>
  )
}
