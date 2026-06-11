/**
 * Screen 2 — Table
 *
 * Top-down view of confirmed layout. 9-ball sequence progress.
 * Tap a ball to select it as the next target, pick a pocket, confirm intention.
 */

import { useState } from 'react'
import { TableView } from '../components/TableView'
import { useSession } from '../store/session'
import type { Pocket } from '../types/pillars'
import { GAME_OBJECT_BALLS } from '../types/pillars'

const POCKET_LABELS: Record<Pocket, string> = {
  'top-left': 'Top Left',
  'top-right': 'Top Right',
  'bottom-left': 'Bottom Left',
  'bottom-right': 'Bottom Right',
  'side-left': 'Side Left',
  'side-right': 'Side Right',
}

// Quick cue-ball destination presets. Coordinates are table-relative
// (width 1.27 m × length 2.54 m, origin bottom-left). Setting coords makes
// the Position zone overlay meaningful, not just the descriptor text.
const W = 1.27
const L = 2.54
interface DestPreset {
  label: string
  descriptor: string
  coords: [number, number]
}
const DESTINATION_PRESETS: DestPreset[] = [
  { label: 'Center', descriptor: 'center table', coords: [W / 2, L / 2] },
  { label: 'Top rail', descriptor: 'up near the top rail', coords: [W / 2, L * 0.8] },
  { label: 'Bottom rail', descriptor: 'down near the bottom rail', coords: [W / 2, L * 0.2] },
  { label: 'Left', descriptor: 'center-left of the table', coords: [W * 0.27, L / 2] },
  { label: 'Right', descriptor: 'center-right of the table', coords: [W * 0.73, L / 2] },
  { label: 'Top-left', descriptor: 'top-left quarter', coords: [W * 0.27, L * 0.78] },
  { label: 'Top-right', descriptor: 'top-right quarter', coords: [W * 0.73, L * 0.78] },
  { label: 'Bot-left', descriptor: 'bottom-left quarter', coords: [W * 0.27, L * 0.22] },
  { label: 'Bot-right', descriptor: 'bottom-right quarter', coords: [W * 0.73, L * 0.22] },
]

export function TableScreen() {
  const {
    balls, sequence, currentBallId,
    selectedPocket, setSelectedPocket,
    destinationDescriptor, setDestinationDescriptor,
    destinationCoords, setDestinationCoords,
    bankRails, setBankRails,
    optimizeSauce, setOptimizeSauce,
    setScreen, setError,
  } = useSession()

  // Beta scope: only the 8 and 9 are shootable targets (not the cue).
  const remainingBalls = balls.filter(
    (b) => b.id !== 'cue' && GAME_OBJECT_BALLS.includes(b.id)
  )

  // 9-ball endgame: always play the 8 first, then the 9.
  const defaultTarget =
    remainingBalls.find((b) => b.id === '8')?.id
    ?? remainingBalls[0]?.id
    ?? null
  const [localTarget, setLocalTarget] = useState<string | null>(defaultTarget)

  // Tap-to-place exact cue target mode.
  const [placeTargetMode, setPlaceTargetMode] = useState(false)

  function handleBallTap(id: string) {
    if (id !== 'cue' && balls.some((b) => b.id === id)) {
      setLocalTarget(id)
    }
  }

  function startShot() {
    if (!localTarget || !selectedPocket) {
      setError('Select a target ball and pocket first.')
      return
    }
    if (!balls.some((b) => b.id === localTarget)) {
      setError(`Ball ${localTarget} is not on the table. Pick a placed ball.`)
      return
    }
    setError(null)
    // Commit the chosen target so ShotScreen requests the right ball.
    useSession.setState({ currentBallId: localTarget })
    setScreen('shot')
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <button
          className="text-gray-500 text-xs tracking-widest"
          onClick={() => useSession.getState().setScreen('capture')}
        >
          ← RESET
        </button>
        <span className="text-xs text-gray-600 tracking-widest uppercase">Table</span>
        <span className="text-xs text-gray-700">{balls.length} balls</span>
      </div>

      {/* Table */}
      <div className="px-3">
        <TableView
          balls={balls}
          currentBallId={localTarget}
          selectedPocket={selectedPocket}
          onPocketSelect={placeTargetMode ? undefined : setSelectedPocket}
          onTableTap={placeTargetMode ? (x, y) => {
            setDestinationCoords([x, y])
            setDestinationDescriptor('exact spot')
            setPlaceTargetMode(false)
          } : undefined}
          destinationZone={
            destinationCoords
              ? { center: destinationCoords, radius_m: 0.18 }
              : undefined
          }
        />
      </div>

      <p className="text-center text-xs text-gray-600 mt-1">
        {placeTargetMode ? 'Tap the table to set the exact cue target' : 'Tap a pocket to select it'}
      </p>

      {/* Target ball selector */}
      <div className="mx-4 mt-3">
        <p className="text-xs text-gray-500 tracking-widest mb-2">TARGET BALL</p>
        <div className="flex gap-2 flex-wrap">
          {remainingBalls.map((b) => (
            <button
              key={b.id}
              onClick={() => handleBallTap(b.id)}
              className={`px-3 py-1.5 rounded text-xs font-bold border transition ${
                localTarget === b.id
                  ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]'
                  : 'border-gray-700 text-gray-400'
              }`}
            >
              {b.id}-ball
            </button>
          ))}
        </div>
      </div>

      {/* Pocket display */}
      {selectedPocket && (
        <div className="mx-4 mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-500">Pocket:</span>
          <span className="text-xs text-[#facc15] font-bold tracking-wide">
            {POCKET_LABELS[selectedPocket]}
          </span>
          <button
            className="ml-auto text-xs text-gray-600"
            onClick={() => setSelectedPocket(null)}
          >
            clear
          </button>
        </div>
      )}

      {/* Shot type — direct or forced bank */}
      <div className="mx-4 mt-3">
        <p className="text-xs text-gray-500 tracking-widest mb-2">SHOT TYPE</p>
        <div className="grid grid-cols-4 gap-1.5">
          {[
            { n: 0, label: 'Direct' },
            { n: 1, label: '1-rail' },
            { n: 2, label: '2-rail' },
            { n: 3, label: '3-rail' },
          ].map((o) => (
            <button
              key={o.n}
              onClick={() => setBankRails(o.n)}
              className={`py-1.5 rounded text-[11px] border transition ${
                bankRails === o.n
                  ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]'
                  : 'border-gray-700 text-gray-400'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Destination — presets + exact tap + free text */}
      <div className="mx-4 mt-3">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-gray-500 tracking-widest">CUE DESTINATION</p>
          <button
            onClick={() => setPlaceTargetMode(!placeTargetMode)}
            className={`text-[10px] tracking-widest px-2 py-1 rounded border transition ${
              placeTargetMode
                ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]'
                : 'border-gray-700 text-gray-400'
            }`}
          >
            {placeTargetMode ? 'TAP TABLE…' : '⊕ EXACT SPOT'}
          </button>
        </div>
        <div className="grid grid-cols-3 gap-1.5 mb-2">
          {DESTINATION_PRESETS.map((p) => {
            const active =
              destinationCoords != null &&
              Math.abs(destinationCoords[0] - p.coords[0]) < 1e-6 &&
              Math.abs(destinationCoords[1] - p.coords[1]) < 1e-6
            return (
              <button
                key={p.label}
                onClick={() => {
                  setDestinationCoords(p.coords)
                  setDestinationDescriptor(p.descriptor)
                }}
                className={`py-1.5 rounded text-[11px] border transition ${
                  active
                    ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]'
                    : 'border-gray-700 text-gray-400'
                }`}
              >
                {p.label}
              </button>
            )
          })}
        </div>
        <input
          type="text"
          value={destinationDescriptor}
          onChange={(e) => {
            setDestinationDescriptor(e.target.value)
            setDestinationCoords(null)   // free text clears the preset target
          }}
          className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-[#facc15]"
          placeholder="or describe it: center table for next shot"
        />
        {destinationCoords && (
          <p className="text-[10px] text-gray-600 mt-1">
            target ({destinationCoords[0].toFixed(2)}, {destinationCoords[1].toFixed(2)}) m
          </p>
        )}

        {/* Advise spin for position — only meaningful with a coordinate target */}
        <button
          onClick={() => setOptimizeSauce(!optimizeSauce)}
          disabled={!destinationCoords}
          className={`mt-2 w-full py-2 rounded text-[11px] border transition flex items-center justify-center gap-2 ${
            !destinationCoords
              ? 'border-gray-800 text-gray-700'
              : optimizeSauce
              ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]'
              : 'border-gray-700 text-gray-400'
          }`}
        >
          <span>{optimizeSauce ? '✓' : '○'}</span>
          ADVISE SPIN FOR POSITION
        </button>
      </div>

      {/* CTA */}
      <div className="mt-auto px-4 pb-8 pt-4">
        <button
          disabled={!localTarget || !selectedPocket}
          onClick={startShot}
          className="w-full py-4 rounded bg-[#facc15] text-black font-bold tracking-widest text-sm disabled:opacity-30 transition"
        >
          COMPUTE SHOT →
        </button>
      </div>
    </div>
  )
}
