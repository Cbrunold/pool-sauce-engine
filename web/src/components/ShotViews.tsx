/**
 * ShotViews — non-top-down camera angles for a shot.
 *
 *  - "cut": look straight down the object-ball → pocket line. The cue/ghost
 *    ball overlaps the object ball by the contact fraction (the eclipse). The
 *    apparent pivot grows with the cut angle (0° = full hit, 90° = edge).
 *  - "low": shooter's-eye, low behind the cue ball during the stroke — the
 *    aim line recedes to the object ball and the pocket with perspective.
 *
 * Both are schematic (computed from cut angle + contact fraction), not photo-
 * real — enough to *feel* the shot the way you'll see it over the table.
 */

interface Props {
  view: 'cut' | 'low'
  cutAngleDeg: number      // signed: negative = cut left, positive = cut right
  contactFraction: number  // 1 = full hit, 0 = edge
  ballColor: string
  ballId: string
  potted?: boolean
}

const CLOTH = '#0e5c2a'

export function ShotViews({ view, cutAngleDeg, contactFraction, ballColor, ballId, potted }: Props) {
  return view === 'cut'
    ? <CutEclipse cutAngleDeg={cutAngleDeg} contactFraction={contactFraction} ballColor={ballColor} ballId={ballId} potted={potted} />
    : <LowAim cutAngleDeg={cutAngleDeg} ballColor={ballColor} ballId={ballId} potted={potted} />
}

/** The cut as seen looking at the pocket: ghost ball eclipsing the object ball. */
function CutEclipse({ cutAngleDeg, contactFraction, ballColor, ballId, potted }: Omit<Props, 'view'>) {
  const W = 320, H = 240
  const cx = W / 2, cy = H * 0.62
  const R = 46
  const cut = Math.abs(cutAngleDeg)
  const dir = cutAngleDeg < 0 ? -1 : 1
  // Lateral offset of the ghost ball center = 2R·sin(cut), capped to edge.
  const offset = Math.min(2 * R, 2 * R * Math.sin((cut * Math.PI) / 180)) * dir

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded bg-[#0a0a0a]">
      {/* Pocket mouth behind the object ball */}
      <ellipse cx={cx} cy={cy - R - 26} rx={34} ry={13} fill="#000" stroke="#222" />
      <rect x={0} y={cy - R - 26} width={W} height={H} fill={CLOTH} opacity={0.18} />

      {/* Object ball */}
      <circle cx={cx} cy={cy} r={R} fill={ballColor} stroke="#000" strokeOpacity={0.4} />
      {ballId === '9' && <ellipse cx={cx} cy={cy} rx={R} ry={R * 0.42} fill="#fff" opacity={0.9} />}

      {/* Ghost / cue ball overlapping at the contact fraction */}
      <circle cx={cx + offset} cy={cy} r={R} fill="#f1f5f9" fillOpacity={0.42} stroke="#f1f5f9" strokeDasharray="4 3" />

      {/* Aim line through centers, to the pocket */}
      <line x1={cx + offset} y1={cy} x2={cx} y2={cy - R - 26} stroke="#facc15" strokeWidth={1.5} strokeDasharray="3 3" opacity={0.8} />

      {/* Contact-point marker on the object ball edge */}
      <circle cx={cx + (offset / 2)} cy={cy - Math.sqrt(Math.max(0, R * R - (offset / 2) ** 2))} r={4} fill="#facc15" />

      <text x={cx} y={26} textAnchor="middle" fill="#9ca3af" fontSize={13} fontFamily="monospace">
        {cut.toFixed(0)}° cut · {fractionLabel(contactFraction)} ball
      </text>
      {potted === false && <text x={cx} y={H - 10} textAnchor="middle" fill="#ef4444" fontSize={12} fontWeight="bold">MISS</text>}
    </svg>
  )
}

/** Shooter's-eye: low behind the cue, aim line receding to the object ball. */
function LowAim({ cutAngleDeg, ballColor, ballId, potted }: Omit<Props, 'view' | 'contactFraction'>) {
  const W = 320, H = 240
  const cueX = W / 2, cueY = H - 28, cueR = 40
  const dir = cutAngleDeg < 0 ? -1 : 1
  const cut = Math.abs(cutAngleDeg)
  // Object ball sits up-table (smaller with distance); offset to the cut side.
  const obX = W / 2 + dir * Math.min(70, cut * 1.6)
  const obY = 84, obR = 22
  // Pocket further up, beyond the object ball along the cut line.
  const pkX = obX + dir * 26, pkY = 44

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded bg-[#0a0a0a]">
      {/* Perspective cloth — trapezoid narrowing toward the top (distance) */}
      <polygon points={`40,${H} ${W - 40},${H} ${W * 0.66},60 ${W * 0.34},60`} fill={CLOTH} opacity={0.5} />

      {/* Pocket */}
      <ellipse cx={pkX} cy={pkY} rx={16} ry={7} fill="#000" stroke="#222" />

      {/* Aim line: cue → object ball → pocket */}
      <line x1={cueX} y1={cueY - cueR} x2={obX} y2={obY} stroke="#f1f5f9" strokeWidth={1.5} strokeDasharray="2 4" opacity={0.9} />
      <line x1={obX} y1={obY} x2={pkX} y2={pkY} stroke="#facc15" strokeWidth={1.5} strokeDasharray="3 3" opacity={0.8} />

      {/* Object ball (far, small) */}
      <circle cx={obX} cy={obY} r={obR} fill={ballColor} stroke="#000" strokeOpacity={0.4} />
      {ballId === '9' && <ellipse cx={obX} cy={obY} rx={obR} ry={obR * 0.42} fill="#fff" opacity={0.9} />}

      {/* Cue ball (near, large) */}
      <circle cx={cueX} cy={cueY} r={cueR} fill="#f1f5f9" stroke="#cbd5e1" />
      {/* Tip contact dot (center for now) */}
      <circle cx={cueX} cy={cueY} r={4} fill="#1e293b" />

      <text x={W / 2} y={22} textAnchor="middle" fill="#9ca3af" fontSize={12} fontFamily="monospace">
        shooter's eye · {cut.toFixed(0)}° cut {dir < 0 ? 'left' : 'right'}
      </text>
      {potted === false && <text x={W / 2} y={H - 6} textAnchor="middle" fill="#ef4444" fontSize={12} fontWeight="bold">MISS</text>}
    </svg>
  )
}

function fractionLabel(frac: number): string {
  const eighths = Math.round(frac * 8)
  const map: Record<number, string> = { 0: 'edge', 2: '¼', 4: '½', 6: '¾', 8: 'full' }
  return map[eighths] ?? `${(frac).toFixed(2)}`
}
