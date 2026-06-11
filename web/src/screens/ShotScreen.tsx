/**
 * Screen 3 — Shot Plan
 *
 * Fetches Pillar I-III plan from API. Renders three visual panels:
 *   A — AngleDiagram (top-down aim line + escape route)
 *   B — PositionTarget (A/B/C zone circles)
 *   C — StrikeInsert (eclipse/clock cue contact)
 *
 * Below: Pillar I-III text in Rō's voice.
 */

import { useEffect, useState } from 'react'
import { AngleDiagram } from '../components/AngleDiagram'
import { PositionTarget } from '../components/PositionTarget'
import { StrikeInsert } from '../components/StrikeInsert'
import { CutView } from '../components/CutView'
import { fetchPlan, fetchCueOptions } from '../api/client'
import { useSession } from '../store/session'
import type { PillarPlan, RankedOption } from '../types/pillars'

const DIFFICULTY_COLOR: Record<string, string> = {
  stock: '#22c55e',
  comfortable: '#84cc16',
  tricky: '#f59e0b',
  hard: '#ef4444',
}

/** A −5..+5 spin stepper: 0 = center, 1–5 each direction. */
function SpinStepper({
  label, value, onChange, negLabel, posLabel,
}: {
  label: string
  value: number
  onChange: (n: number) => void
  negLabel: string
  posLabel: string
}) {
  const readout =
    value === 0 ? 'Center' : `${value > 0 ? posLabel : negLabel} ${Math.abs(value)}`
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-gray-500 tracking-widest w-14">{label}</span>
      <button
        onClick={() => onChange(value - 1)}
        className="w-8 h-8 rounded border border-gray-700 text-gray-300 text-lg leading-none disabled:opacity-30"
        disabled={value <= -5}
      >−</button>
      {/* 11-segment bar centered on 0 */}
      <div className="flex-1 flex items-center gap-0.5">
        {Array.from({ length: 11 }, (_, i) => i - 5).map((n) => {
          const active =
            n === 0 ? value === 0
            : value > 0 ? n > 0 && n <= value
            : n < 0 && n >= value
          return (
            <div
              key={n}
              className={`flex-1 h-2 rounded-sm ${
                n === 0 ? 'bg-gray-600' : active ? 'bg-[#facc15]' : 'bg-gray-800'
              }`}
            />
          )
        })}
      </div>
      <button
        onClick={() => onChange(value + 1)}
        className="w-8 h-8 rounded border border-gray-700 text-gray-300 text-lg leading-none disabled:opacity-30"
        disabled={value >= 5}
      >+</button>
      <span className="text-[10px] text-[#facc15] w-16 text-right font-mono">{readout}</span>
    </div>
  )
}

export function ShotScreen() {
  const {
    balls, currentBallId, selectedPocket,
    destinationDescriptor, destinationCoords, bankRails, optimizeSauce,
    manualSpin, setManualSpin, spinV, setSpinV, spinH, setSpinH,
    setCurrentPlan, setScreen, setError, error,
  } = useSession()

  const [plan, setPlan] = useState<PillarPlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [options, setOptions] = useState<RankedOption[]>([])
  const [chosen, setChosen] = useState<RankedOption | null>(null)

  const tableState = {
    table_size_m: [2.54, 1.27] as [number, number],
    balls,
  }

  useEffect(() => {
    if (!currentBallId || !selectedPocket) {
      setScreen('table')
      return
    }

    // Manual spin overrides the auto-advice when engaged.
    const spinOverride = manualSpin
      ? { vertical_tips: spinV / 5, horizontal_tips: spinH / 5 }
      : {}

    fetchPlan({
      state: tableState,
      intention: {
        target_ball_id: currentBallId,
        pocket: selectedPocket,
        destination_descriptor: destinationDescriptor,
        destination_coordinates_m: destinationCoords ?? undefined,
      },
      sauce: {
        english: 'none', stroke: 'spoon of stun',
        force: 'measured', acceleration: 'controlled',
        ...spinOverride,
      },
      shot_id: `shot-${currentBallId}`,
      bank_rails: bankRails,
      optimize_sauce: manualSpin ? false : optimizeSauce,
    })
      .then((res) => {
        setPlan(res.plan)
        setCurrentPlan(res.plan)
        setError(null)
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false))

    // Ranked stroke options — only for a direct shot to an exact spot.
    setOptions([])
    setChosen(null)
    if (bankRails === 0 && destinationCoords && currentBallId && selectedPocket) {
      fetchCueOptions({
        state: tableState,
        intention: {
          target_ball_id: currentBallId,
          pocket: selectedPocket,
          destination_descriptor: destinationDescriptor,
        },
        target_position_m: destinationCoords,
      })
        .then((res) => setOptions(res.options))
        .catch(() => setOptions([]))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBallId, selectedPocket, bankRails, optimizeSauce, manualSpin, spinV, spinH])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white gap-4">
        <div className="w-8 h-8 border-2 border-[#facc15] border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400 text-sm tracking-widest">
          {bankRails > 0 ? 'SEARCHING THE RAILS' : 'COMPUTING THE LINE'}
        </p>
      </div>
    )
  }

  if (error || !plan) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white px-6 gap-4">
        <p className="text-red-400 text-sm text-center">{error ?? 'Shot could not be computed.'}</p>
        <button
          className="text-[#facc15] text-sm tracking-widest"
          onClick={() => setScreen('table')}
        >
          ← BACK TO TABLE
        </button>
      </div>
    )
  }

  const p1 = plan.pillar_I as Record<string, unknown>
  const p2 = plan.pillar_II as Record<string, unknown>
  const p3 = plan.pillar_III as Record<string, unknown>

  // A chosen ranked option overrides the plan's default sauce for the inserts.
  const english = chosen?.english ?? (p3?.english as Record<string, unknown>)?.sauce_term as string ?? 'none'
  const stroke  = chosen?.stroke  ?? (p3?.stroke  as Record<string, unknown>)?.sauce_term as string ?? 'spoon of stun'
  const force   = p3?.force as string ?? 'measured'
  const accel   = p3?.acceleration as string ?? 'controlled'
  const recipe  = p3?.recipe_rationale as string ?? ''

  const speedWindow = p2?.speed_window as Record<string, unknown>
  const speedLabel  = speedWindow?.label as string ?? 'medium'

  const destination = (p1?.destination as Record<string, unknown>)
  const destCoordsArr = destination?.coordinates_m as number[] | undefined  // [x_m, y_m]
  const destCoords = destCoordsArr && destCoordsArr.length >= 2
    ? { x_m: destCoordsArr[0], y_m: destCoordsArr[1] }
    : undefined

  const contactPoint = p2?.contact_point as Record<string, unknown> | undefined
  const cutMagnitude = (contactPoint?.cut_angle_deg as number) ?? 0
  const contactFraction = contactPoint?.ball_fraction as number | undefined

  // Derive cut direction (sign) from geometry: side of the aim line the
  // object ball sits on. Negative = cut left, positive = cut right.
  const cutAngleDeg = (() => {
    try {
      const v = (p2?.line_of_aim as Record<string, unknown>)?.vector as number[]
      const ts = plan.table_state as Record<string, unknown>
      const tsBalls = ts?.balls as { id: string; x_m: number; y_m: number }[]
      const target = tsBalls?.find((b) => b.id === currentBallId)
      if (!v || v.length < 4 || !target) return cutMagnitude
      const [cx, cy, gx, gy] = v
      const dx = gx - cx, dy = gy - cy
      const cross = dx * (target.y_m - gy) - dy * (target.x_m - gx)
      return cross < 0 ? -cutMagnitude : cutMagnitude
    } catch {
      return cutMagnitude
    }
  })()

  const doctrine = plan.doctrine_line as string | undefined

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <button
          className="text-gray-500 text-xs tracking-widest"
          onClick={() => setScreen('table')}
        >
          ← TABLE
        </button>
        <span className="text-xs text-[#facc15] tracking-widest font-bold">
          {currentBallId}-BALL → {selectedPocket?.toUpperCase()}
        </span>
        <span className="text-xs text-gray-700">{speedLabel}</span>
      </div>

      {/* Visual panels — angle diagram spans, then 3 inserts */}
      <div className="px-3 py-2 space-y-2">
        {/* Angle diagram — full width */}
        <div className="flex flex-col items-center gap-1">
          <AngleDiagram plan={plan} balls={balls} />
          <span className="text-[9px] text-gray-600 tracking-widest">THE PATH</span>
        </div>

        {/* Three inserts: cut · position · strike */}
        <div className="grid grid-cols-3 gap-2">
          {/* Cut view — real PoolShot aiming card */}
          <div className="flex flex-col items-center gap-1">
            <CutView cutAngleDeg={cutAngleDeg} ballId={currentBallId ?? '1'} contactFraction={contactFraction} />
            <span className="text-[9px] text-gray-600 tracking-widest">THE CUT</span>
          </div>

          {/* Position target */}
          <div className="flex flex-col items-center gap-1">
            <PositionTarget
              destinationCoords={destCoords ? [destCoords.x_m, destCoords.y_m] : null}
            />
            <span className="text-[9px] text-gray-600 tracking-widest">POSITION</span>
          </div>

          {/* Strike insert — cue ball contact */}
          <div className="flex flex-col items-center gap-1">
            <StrikeInsert
              english={english}
              stroke={stroke}
              tipOffsetX={manualSpin ? spinH / 5 : undefined}
              tipOffsetY={manualSpin ? spinV / 5 : undefined}
            />
            <span className="text-[9px] text-gray-600 tracking-widest">THE SAUCE</span>
          </div>
        </div>
      </div>

      {/* Manual spin control */}
      <div className="mx-4 mt-2">
        <button
          onClick={() => setManualSpin(!manualSpin)}
          className={`w-full py-2 rounded text-[11px] border tracking-widest transition flex items-center justify-center gap-2 ${
            manualSpin
              ? 'border-[#facc15] text-[#facc15] bg-[#facc1510]'
              : 'border-gray-700 text-gray-400'
          }`}
        >
          <span>{manualSpin ? '✓' : '○'}</span>
          DIAL SPIN MANUALLY
        </button>

        {manualSpin && (
          <div className="mt-2 space-y-2">
            <SpinStepper
              label="VERTICAL"
              value={spinV}
              onChange={setSpinV}
              negLabel="Draw"
              posLabel="Top"
            />
            <SpinStepper
              label="SIDE"
              value={spinH}
              onChange={setSpinH}
              negLabel="Left"
              posLabel="Right"
            />
          </div>
        )}
      </div>

      {/* Ranked stroke options — exact-target shots only */}
      {options.length > 0 && (
        <div className="mx-4 mt-1">
          <p className="text-[10px] text-gray-500 tracking-widest mb-2">
            OPTIONS · MOST REPLICABLE FIRST
          </p>
          <div className="space-y-1.5">
            {options.map((o) => {
              const active = chosen?.rank === o.rank
              const color = DIFFICULTY_COLOR[o.difficulty_label] ?? '#888'
              return (
                <button
                  key={o.rank}
                  onClick={() => setChosen(active ? null : o)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded border text-left transition ${
                    active ? 'border-[#facc15] bg-[#facc1510]' : 'border-gray-800'
                  }`}
                >
                  <span className="text-[10px] font-mono text-gray-600 w-4">{o.rank}</span>
                  <span
                    className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide"
                    style={{ color, borderColor: color, border: `1px solid ${color}` }}
                  >
                    {o.difficulty_label}
                  </span>
                  <span className="text-[11px] text-white flex-1">
                    {o.stroke}{o.english !== 'none' ? ` · ${o.english}` : ''}
                  </span>
                  <span className="text-[9px] text-gray-500 font-mono">
                    {o.makeable ? `±${(o.landing_error_m * 100).toFixed(0)}cm` : 'misses zone'}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Pillar text */}
      <div className="mx-4 mt-2 space-y-4 text-xs">

        {/* Pillar I */}
        <section className="border-l-2 border-[#facc15] pl-3">
          <p className="text-[#facc15] tracking-widest text-[10px] mb-1">— PILLAR I · INTENTION —</p>
          <p><span className="text-gray-500">Target:</span> <span className="text-white">{currentBallId}-ball</span></p>
          <p><span className="text-gray-500">Pocket:</span> <span className="text-white">{selectedPocket}</span></p>
          <p><span className="text-gray-500">Destination:</span> <span className="text-white">{destinationDescriptor}</span></p>
        </section>

        {/* Pillar II */}
        <section className="border-l-2 border-gray-700 pl-3">
          <p className="text-gray-400 tracking-widest text-[10px] mb-1">— PILLAR II · THE PATH —</p>
          <p><span className="text-gray-500">Speed window:</span> <span className="text-white">{speedLabel}</span></p>
          {(p2?.rails_involved as string[])?.length > 0 && (
            <p><span className="text-gray-500">Rails:</span> <span className="text-white">{(p2.rails_involved as string[]).join(', ')}</span></p>
          )}
          {(p2?.contact_point as Record<string, unknown>)?.cut_angle_deg !== undefined && (
            <p>
              <span className="text-gray-500">Cut:</span>{' '}
              <span className="text-white">
                {Math.round((p2.contact_point as Record<string, unknown>).cut_angle_deg as number)}°
              </span>
            </p>
          )}
        </section>

        {/* Pillar III */}
        <section className="border-l-2 border-gray-700 pl-3">
          <p className="text-gray-400 tracking-widest text-[10px] mb-1">— PILLAR III · THE SAUCE —</p>
          <p><span className="text-gray-500">English:</span> <span className="text-white">{english}</span></p>
          <p><span className="text-gray-500">Stroke:</span> <span className="text-white">{stroke}</span></p>
          <p><span className="text-gray-500">Force:</span> <span className="text-white">{force}</span></p>
          <p><span className="text-gray-500">Acceleration:</span> <span className="text-white">{accel}</span></p>
          {recipe && (
            <p className="mt-1 text-gray-300 italic">{recipe}</p>
          )}
        </section>

        {/* Pillar IV */}
        <section className="border-l-2 border-gray-800 pl-3">
          <p className="text-gray-600 tracking-widest text-[10px] mb-1">— PILLAR IV · EXECUTION —</p>
          <p className="text-gray-600 italic">(Yours, warrior.)</p>
        </section>

        {/* Doctrine */}
        {doctrine && (
          <p className="text-gray-500 italic text-center text-[11px] pt-1">
            {doctrine}
          </p>
        )}
      </div>

      {/* CTA */}
      <div className="mt-auto px-4 pb-8 pt-6">
        <button
          onClick={() => setScreen('debrief')}
          className="w-full py-4 rounded bg-[#facc15] text-black font-bold tracking-widest text-sm transition"
        >
          SHOT TAKEN →
        </button>
      </div>
    </div>
  )
}
