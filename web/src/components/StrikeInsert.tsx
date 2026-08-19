/**
 * StrikeInsert — eclipse/clock-face cue ball contact diagram.
 *
 * Shows where the tip contacts the cue ball and what spin results.
 * English tip offset: x = horizontal (right positive), y = vertical (up positive).
 * Labels use Sauce vocabulary.
 */

interface Props {
  english?: string    // Sauce phrase e.g. "a drop of right"
  stroke?: string     // Sauce phrase e.g. "a zest of follow"
  tipOffsetX?: number // -1 to 1 (horizontal, right positive)
  tipOffsetY?: number // -1 to 1 (vertical, up positive)
  className?: string
}

const SIZE = 160
const CX = SIZE / 2
const CY = SIZE / 2
const BALL_R = 56
const DOT_R = 6

// Parse tip offsets from Sauce phrase if not provided directly
function parseTipFromPhrase(phrase: string): number {
  if (!phrase) return 0
  const p = phrase.toLowerCase()
  if (p.includes('healthy pour') || p.includes('full')) return p.includes('right') || p.includes('follow') ? 1.0 : -1.0
  if (p.includes('drop')) return p.includes('right') ? 0.5 : p.includes('left') ? -0.5 : 0
  if (p.includes('pinch')) return p.includes('right') ? 0.25 : p.includes('left') ? -0.25 : 0
  if (p.includes('zest')) return 0.25
  if (p.includes('whisper')) return -0.25
  if (p.includes('draw')) return -1.0
  if (p.includes('follow')) return 1.0
  return 0
}

export function StrikeInsert({
  english = 'none',
  stroke = 'spoon of stun',
  tipOffsetX,
  tipOffsetY,
  className = '',
}: Props) {
  const ox = tipOffsetX ?? parseTipFromPhrase(english)
  const oy = tipOffsetY ?? parseTipFromPhrase(stroke)

  // Tip dot position in SVG coords
  const dotX = CX + ox * BALL_R * 0.72
  const dotY = CY - oy * BALL_R * 0.72  // SVG y flipped

  // Spin arrow vectors (English = horizontal, vertical = stroke)
  const hasEnglish = Math.abs(ox) > 0.1
  const hasVertical = Math.abs(oy) > 0.1

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className={`w-full max-w-[160px] ${className}`}
      aria-label="Cue ball contact point"
    >
      {/* Outer glow ring */}
      <circle cx={CX} cy={CY} r={BALL_R + 6} fill="none" stroke="#facc1520" strokeWidth={3} />

      {/* Ball body */}
      <circle cx={CX} cy={CY} r={BALL_R} fill="#1a1a1a" stroke="#3a3a3a" strokeWidth={1.5} />

      {/* Clock guides — faint */}
      {[0, 90, 180, 270].map((deg) => {
        const rad = (deg * Math.PI) / 180
        const x1 = CX + Math.cos(rad) * (BALL_R - 12)
        const y1 = CY + Math.sin(rad) * (BALL_R - 12)
        const x2 = CX + Math.cos(rad) * BALL_R
        const y2 = CY + Math.sin(rad) * BALL_R
        return <line key={deg} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#ffffff18" strokeWidth={1} />
      })}

      {/* Centre crosshair */}
      <line x1={CX - BALL_R * 0.35} y1={CY} x2={CX + BALL_R * 0.35} y2={CY} stroke="#ffffff20" strokeWidth={0.8} />
      <line x1={CX} y1={CY - BALL_R * 0.35} x2={CX} y2={CY + BALL_R * 0.35} stroke="#ffffff20" strokeWidth={0.8} />

      {/* Spin arrows — English (horizontal) */}
      {hasEnglish && (
        <g opacity={0.85}>
          {ox > 0 ? (
            // Right english: arrow curving right
            <path
              d={`M ${CX - 8} ${CY + BALL_R * 0.6} Q ${CX + BALL_R * 0.5} ${CY + BALL_R * 0.75} ${CX + BALL_R * 0.65} ${CY + BALL_R * 0.35}`}
              fill="none" stroke="#38bdf8" strokeWidth={1.5}
              markerEnd="url(#arrowBlue)"
            />
          ) : (
            <path
              d={`M ${CX + 8} ${CY + BALL_R * 0.6} Q ${CX - BALL_R * 0.5} ${CY + BALL_R * 0.75} ${CX - BALL_R * 0.65} ${CY + BALL_R * 0.35}`}
              fill="none" stroke="#38bdf8" strokeWidth={1.5}
              markerEnd="url(#arrowBlue)"
            />
          )}
        </g>
      )}

      {/* Spin arrows — vertical (follow/draw) */}
      {hasVertical && (
        <g opacity={0.85}>
          {oy > 0 ? (
            // Follow: arrow pointing up on right side
            <path
              d={`M ${CX + BALL_R * 0.65} ${CY + 8} L ${CX + BALL_R * 0.65} ${CY - 18}`}
              fill="none" stroke="#a78bfa" strokeWidth={1.5}
              markerEnd="url(#arrowPurple)"
            />
          ) : (
            // Draw: arrow pointing down on right side
            <path
              d={`M ${CX + BALL_R * 0.65} ${CY - 8} L ${CX + BALL_R * 0.65} ${CY + 18}`}
              fill="none" stroke="#a78bfa" strokeWidth={1.5}
              markerEnd="url(#arrowPurple)"
            />
          )}
        </g>
      )}

      {/* Tip contact dot */}
      <circle cx={dotX} cy={dotY} r={DOT_R + 2} fill="#facc1540" />
      <circle cx={dotX} cy={dotY} r={DOT_R} fill="#facc15" />

      {/* Label: clock position */}
      <text x={CX} y={SIZE - 4} textAnchor="middle" fontSize={9} fill="#888" fontFamily="monospace">
        {english === 'none' ? stroke : `${english} · ${stroke}`}
      </text>

      {/* Arrow markers */}
      <defs>
        <marker id="arrowBlue" markerWidth={6} markerHeight={6} refX={3} refY={3} orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="#38bdf8" />
        </marker>
        <marker id="arrowPurple" markerWidth={6} markerHeight={6} refX={3} refY={3} orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="#a78bfa" />
        </marker>
      </defs>
    </svg>
  )
}
