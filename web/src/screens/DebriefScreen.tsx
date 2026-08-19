/**
 * Screen 4 — Debrief
 *
 * Tap the table where the cue ball actually landed → POST /api/debrief.
 * Optional override chips for spin verdict, pace, correct side.
 * Renders Pillar V. "Next Shot" advances the sequence and returns to Table.
 */

import { useState } from 'react'
import { TableView } from '../components/TableView'
import { PositionTarget } from '../components/PositionTarget'
import { fetchDebrief } from '../api/client'
import { useSession } from '../store/session'
import type { PillarPlan, SpinVerdict, PaceControl, CorrectSide } from '../types/pillars'

const SPIN_OPTIONS: SpinVerdict[] = ['clean', 'too much', 'not enough', 'wrong axis', 'overcooked', 'undercooked']
const PACE_OPTIONS: PaceControl[] = ['clean', 'punchy', 'decelerated', 'floated', 'stunned-late', 'stunned-early']
const SIDE_OPTIONS: CorrectSide[] = ['natural', 'forced', 'high', 'low']

export function DebriefScreen() {
  const {
    balls, currentPlan,
    actualCuePosition, setActualCuePosition,
    advanceSequence, setScreen, updateBall,
    setCurrentPlan, setError, error,
  } = useSession()

  const [spin, setSpin] = useState<SpinVerdict>('clean')
  const [pace, setPace] = useState<PaceControl | null>(null)
  const [side, setSide] = useState<CorrectSide>('natural')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PillarPlan | null>(null)

  function handleTableTap(x_m: number, y_m: number) {
    setActualCuePosition([x_m, y_m])
    // Update cue ball in table state for visual feedback
    updateBall('cue', x_m, y_m)
  }

  async function submitDebrief() {
    if (!currentPlan) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetchDebrief({
        plan: currentPlan,
        actual_cue_position_m: actualCuePosition ?? undefined,
        overrides: { spin_verdict: spin, pace_control: pace, correct_side: side },
      })
      setResult(res.plan)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  function nextShot() {
    advanceSequence()
    setActualCuePosition(null)
    setCurrentPlan(null)
    setResult(null)
    setScreen('table')
  }

  const p5 = result?.pillar_V as Record<string, unknown> | undefined

  // Zone
  const zoneLanding = (p5?.zone_landing as Record<string, unknown>)?.zone as string | undefined
  const zoneColor = zoneLanding === 'A' ? 'text-green-400' : zoneLanding === 'B' ? 'text-amber-400' : 'text-red-400'

  // Mastery
  const mastery = p5?.mastery_one_percent as Record<string, unknown> | undefined

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <button
          className="text-gray-500 text-xs tracking-widest"
          onClick={() => setScreen('shot')}
        >
          ← BACK
        </button>
        <span className="text-xs text-gray-600 tracking-widest uppercase">Debrief</span>
        <span className="text-xs text-gray-700" />
      </div>

      {!result ? (
        <>
          {/* Tap-to-place instruction */}
          <p className="text-center text-xs text-gray-500 px-4 mt-1">
            Tap where the cue ball landed.
          </p>

          {/* Table */}
          <div className="px-3 mt-2">
            <TableView
              balls={balls}
              onTableTap={handleTableTap}
              highlightBalls={actualCuePosition ? ['cue'] : []}
            />
          </div>

          {actualCuePosition && (
            <p className="text-center text-xs text-[#facc15] mt-1">
              Cue placed at ({actualCuePosition[0].toFixed(2)}, {actualCuePosition[1].toFixed(2)}) m
            </p>
          )}

          {/* Override chips */}
          <div className="mx-4 mt-4 space-y-3">
            <div>
              <p className="text-[10px] text-gray-500 tracking-widest mb-1.5">SPIN</p>
              <div className="flex flex-wrap gap-1.5">
                {SPIN_OPTIONS.map((v) => (
                  <button
                    key={v}
                    onClick={() => setSpin(v)}
                    className={`px-2.5 py-1 rounded text-[10px] border transition ${
                      spin === v ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]' : 'border-gray-700 text-gray-500'
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-[10px] text-gray-500 tracking-widest mb-1.5">PACE</p>
              <div className="flex flex-wrap gap-1.5">
                <button
                  onClick={() => setPace(null)}
                  className={`px-2.5 py-1 rounded text-[10px] border transition ${
                    pace === null ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]' : 'border-gray-700 text-gray-500'
                  }`}
                >
                  auto
                </button>
                {PACE_OPTIONS.map((v) => (
                  <button
                    key={v}
                    onClick={() => setPace(v)}
                    className={`px-2.5 py-1 rounded text-[10px] border transition ${
                      pace === v ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]' : 'border-gray-700 text-gray-500'
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-[10px] text-gray-500 tracking-widest mb-1.5">SIDE</p>
              <div className="flex gap-1.5">
                {SIDE_OPTIONS.map((v) => (
                  <button
                    key={v}
                    onClick={() => setSide(v)}
                    className={`px-2.5 py-1 rounded text-[10px] border transition ${
                      side === v ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]' : 'border-gray-700 text-gray-500'
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {error && <p className="mx-4 mt-3 text-xs text-red-400">{error}</p>}

          <div className="mt-auto px-4 pb-8 pt-4">
            <button
              onClick={submitDebrief}
              disabled={loading}
              className="w-full py-4 rounded bg-[#facc15] text-black font-bold tracking-widest text-sm disabled:opacity-50 transition"
            >
              {loading ? 'COMPUTING…' : 'SUBMIT DEBRIEF →'}
            </button>
          </div>
        </>
      ) : (
        /* Pillar V result */
        <>
          <div className="mx-4 mt-3 space-y-3 text-xs">
            <p className="text-[#facc15] tracking-widest text-[10px]">— PILLAR V · DEBRIEF —</p>

            {zoneLanding && (
              <p>
                <span className="text-gray-500">Zone landing: </span>
                <span className={`font-bold ${zoneColor}`}>{zoneLanding}</span>
                {(p5?.zone_landing as Record<string, unknown>)?.reason && (
                  <span className="text-gray-400 ml-1">
                    — {(p5!.zone_landing as Record<string, unknown>).reason as string}
                  </span>
                )}
              </p>
            )}

            {/* Zone visual */}
            <div className="flex justify-center py-2">
              <PositionTarget
                destinationCoords={actualCuePosition}
                actualPosition={actualCuePosition}
                zone={zoneLanding as 'A' | 'B' | 'C'}
              />
            </div>

            {p5?.correct_side && (
              <p><span className="text-gray-500">Correct side: </span><span className="text-white">{p5.correct_side as string}</span></p>
            )}

            {p5?.spin_review && (
              <p><span className="text-gray-500">Spin: </span><span className="text-white">{(p5.spin_review as Record<string, unknown>).verdict as string}</span>
                {(p5.spin_review as Record<string, unknown>).notes && (
                  <span className="text-gray-400 ml-1">— {(p5.spin_review as Record<string, unknown>).notes as string}</span>
                )}
              </p>
            )}

            {p5?.pace_control && (
              <p><span className="text-gray-500">Pace: </span><span className="text-white">{p5.pace_control as string}</span></p>
            )}

            {p5?.risk_zones_crossed && (p5.risk_zones_crossed as string[]).length > 0 && (
              <p><span className="text-gray-500">Risk: </span><span className="text-amber-400">{(p5.risk_zones_crossed as string[]).join(', ')}</span></p>
            )}

            {mastery && (
              <div className="mt-3 border-l-2 border-[#facc15] pl-3 space-y-1">
                <p className="text-[10px] text-gray-500 tracking-widest">MASTERY 1%</p>
                <p><span className="text-green-400">Excellent → </span><span className="text-white">{mastery.excellent as string}</span></p>
                <p><span className="text-amber-400">Fragile → </span><span className="text-white">{mastery.fragile as string}</span></p>
              </div>
            )}

            {result?.doctrine_line && (
              <p className="text-gray-500 italic text-center text-[11px] pt-2">
                {result.doctrine_line as string}
              </p>
            )}
          </div>

          <div className="mt-auto px-4 pb-8 pt-6">
            <button
              onClick={nextShot}
              className="w-full py-4 rounded bg-[#facc15] text-black font-bold tracking-widest text-sm transition"
            >
              NEXT SHOT →
            </button>
          </div>
        </>
      )}
    </div>
  )
}
