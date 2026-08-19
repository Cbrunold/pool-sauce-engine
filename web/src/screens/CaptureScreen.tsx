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

/** Read the persisted last error (survives a reload), for on-screen diagnosis. */
function readLastError(): { label: string; msg: string } | null {
  try {
    const raw = localStorage.getItem('pse_last_error')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * Downscale an image File to a JPEG Blob with a max dimension, using the
 * browser's native decoder (handles HEIC on iOS) and a canvas re-encode.
 * Keeps uploads small and guarantees a format OpenCV can read.
 */
async function downscaleToJpeg(file: File, maxDim: number): Promise<File> {
  // Memory-safe path: ask the decoder to resize *while* decoding, so a 12MP
  // phone photo never materializes at full resolution (which crashes/reloads
  // iOS Safari under memory pressure). resizeWidth caps the width; height
  // scales proportionally. We only downscale, never upscale.
  let bitmap: ImageBitmap | null = null
  try {
    const probe = await createImageBitmap(file)
    const longest = Math.max(probe.width, probe.height)
    if (longest <= maxDim) {
      bitmap = probe
    } else {
      const scale = maxDim / longest
      const rw = Math.round(probe.width * scale)
      const rh = Math.round(probe.height * scale)
      probe.close()
      bitmap = await createImageBitmap(file, {
        resizeWidth: rw,
        resizeHeight: rh,
        resizeQuality: 'medium',
      })
    }
  } catch {
    bitmap = null
  }

  let source: CanvasImageSource
  let w: number
  let h: number
  let cleanup: (() => void) | null = null

  if (bitmap) {
    source = bitmap
    w = bitmap.width
    h = bitmap.height
    cleanup = () => bitmap!.close()
  } else {
    // Fallback for decoders without createImageBitmap resize support.
    const url = URL.createObjectURL(file)
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('Could not decode the photo.'))
      el.src = url
    })
    const scale = Math.min(1, maxDim / Math.max(img.naturalWidth, img.naturalHeight))
    w = Math.round(img.naturalWidth * scale)
    h = Math.round(img.naturalHeight * scale)
    source = img
    cleanup = () => URL.revokeObjectURL(url)
  }

  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) { cleanup?.(); throw new Error('Canvas not available for image processing.') }
  ctx.drawImage(source, 0, 0, w, h)
  cleanup?.()

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', 0.85)
  )
  // Release the canvas backing store promptly.
  canvas.width = 0
  canvas.height = 0
  if (!blob) throw new Error('Could not encode the photo.')
  return new File([blob], 'table.jpg', { type: 'image/jpeg' })
}

export function CaptureScreen() {
  const { setBalls, setScreen, setError } = useSession()
  const [mode, setMode] = useState<Mode>('menu')
  const [loading, setLoading] = useState(false)
  const [detected, setDetected] = useState<DetectedBall[]>([])
  const [localBalls, setLocalBalls] = useState<BallState[]>([])
  const cameraRef = useRef<HTMLInputElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)

  // ---- Camera mode ----

  async function handleImageFile(file: File) {
    setLoading(true)
    setError(null)
    try {
      // Downscale + transcode to JPEG before upload. Phone photos are 12MP+
      // and often HEIC (which OpenCV can't decode); a ~1600px JPEG uploads
      // fast and the vision pipeline handles it in well under a second.
      const prepared = await downscaleToJpeg(file, 1280)
      const result = await fetchDetect(prepared)
      const balls: BallState[] = result.balls
        .filter((b) => b.id !== null)
        .map((b) => ({ id: b.id!, x_m: b.x_m, y_m: b.y_m }))
      setDetected(result.balls)
      setLocalBalls(balls)
    } catch (e) {
      const msg = (e as Error).message || 'Could not read the photo. Try manual placement.'
      try {
        localStorage.setItem('pse_last_error', JSON.stringify({
          label: 'detect', msg, at: new Date().toISOString(),
        }))
      } catch { /* ignore */ }
      setError(msg)
      setMode('menu')
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
    const lastError = readLastError()
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white px-6 gap-6">
        {lastError && (
          <div className="w-full max-w-xs p-3 rounded border border-red-700/50 bg-red-900/15 text-left">
            <p className="text-[10px] text-red-400 tracking-widest mb-1">LAST ERROR ({lastError.label})</p>
            <p className="text-[11px] text-gray-300 break-words">{lastError.msg}</p>
            <button
              className="mt-2 text-[10px] text-gray-500"
              onClick={() => { localStorage.removeItem('pse_last_error'); setMode('manual'); setMode('menu') }}
            >
              dismiss
            </button>
          </div>
        )}
        <div className="text-center mb-4">
          <h1 className="text-2xl font-bold tracking-widest text-[#facc15]">RŌ</h1>
          <p className="text-xs text-gray-500 mt-1 tracking-widest uppercase">Pool Sauce Engine</p>
        </div>
        <p className="text-sm text-gray-400 text-center">Set the table. Choose your method.</p>
        <button
          className="w-full max-w-xs py-4 rounded border border-[#facc15] text-[#facc15] tracking-widest text-sm font-bold hover:bg-[#facc1510] transition"
          onClick={() => { setMode('camera'); cameraRef.current?.click() }}
        >
          TAKE A PHOTO
        </button>
        <button
          className="w-full max-w-xs py-4 rounded border border-gray-500 text-gray-200 tracking-widest text-sm hover:bg-white/5 transition"
          onClick={() => { setMode('camera'); uploadRef.current?.click() }}
        >
          UPLOAD A PHOTO
        </button>
        <button
          className="w-full max-w-xs py-4 rounded border border-gray-600 text-gray-300 tracking-widest text-sm hover:bg-white/5 transition"
          onClick={() => setMode('manual')}
        >
          PLACE BALLS MANUALLY
        </button>
        {/* Camera capture (rear) */}
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            e.target.value = ''
            if (f) handleImageFile(f)
          }}
        />
        {/* Library / file upload */}
        <input
          ref={uploadRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            e.target.value = ''
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
