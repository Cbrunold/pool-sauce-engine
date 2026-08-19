/**
 * CutView — object-ball cut diagram (the "eclipse phases" insert).
 *
 * Renders the real PoolShot AimingCard for the computed cut angle, snapped to
 * the nearest available card. Shows the ghost ball overlapping the object ball
 * at the contact fraction — how much of the object ball to hit.
 */

import { aimingCardSrc } from '../overlays/catalog'

interface Props {
  cutAngleDeg: number   // signed: negative = cut left, positive = cut right
  ballId: string
  contactFraction?: number   // 0–1, for the caption
  className?: string
}

export function CutView({ cutAngleDeg, ballId, contactFraction, className = '' }: Props) {
  const src = aimingCardSrc(cutAngleDeg, ballId)
  const dir = cutAngleDeg < -1 ? 'left' : cutAngleDeg > 1 ? 'right' : 'straight'

  return (
    <div className={`flex flex-col items-center ${className}`}>
      <div className="bg-white rounded overflow-hidden border border-gray-700 w-full max-w-[160px] aspect-[5/3] flex items-center justify-center">
        <img
          src={src}
          alt={`Cut ${Math.abs(cutAngleDeg).toFixed(0)}° ${dir}`}
          className="w-full h-full object-contain"
          draggable={false}
        />
      </div>
      <p className="text-[9px] text-gray-600 mt-1 tracking-wide font-mono">
        {Math.abs(cutAngleDeg).toFixed(0)}° {dir}
        {contactFraction !== undefined && ` · ${fractionLabel(contactFraction)}`}
      </p>
    </div>
  )
}

/** Snap a 0–1 contact fraction to the nearest eighth, as a fraction string. */
function fractionLabel(frac: number): string {
  const eighths = Math.round(frac * 8)
  const map: Record<number, string> = {
    0: 'edge', 1: '⅛', 2: '¼', 3: '⅜', 4: '½',
    5: '⅝', 6: '¾', 7: '⅞', 8: 'full',
  }
  return map[Math.max(0, Math.min(8, eighths))] ?? '½'
}
