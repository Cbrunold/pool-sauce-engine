/**
 * PositionTarget — A/B/C zone circles with approach-line median.
 *
 * Zoomed view centred on the destination zone. Shows three concentric rings
 * (A=green, B=amber, C=red) and a directional line indicating the ideal
 * approach angle for the next shot.
 */

interface Props {
  destinationCoords: [number, number] | null
  nextShotDirection?: [number, number]  // unit vector toward next shot target
  actualPosition?: [number, number] | null
  zone?: 'A' | 'B' | 'C' | null
  className?: string
}

const SIZE = 160
const CX = SIZE / 2
const CY = SIZE / 2

// Zone radii in SVG pixels (C outer, B middle, A inner)
const R_C = 66
const R_B = 44
const R_A = 22

export function PositionTarget({
  destinationCoords,
  nextShotDirection,
  actualPosition,
  zone,
  className = '',
}: Props) {
  // Approach line: from centre outward (shows where to come from)
  const [dx, dy] = nextShotDirection ?? [0, 1]
  const lineLen = R_C + 10
  const lx2 = CX - dx * lineLen  // show approach FROM that direction
  const ly2 = CY + dy * lineLen  // SVG y flipped

  // Actual landing dot (relative to destination — offset in zone coords)
  let dotX = CX
  let dotY = CY
  let showDot = false
  if (actualPosition && destinationCoords) {
    const offX = (actualPosition[0] - destinationCoords[0]) / 0.3 * R_C
    const offY = (actualPosition[1] - destinationCoords[1]) / 0.3 * R_C
    dotX = CX + offX
    dotY = CY - offY // SVG y flipped
    showDot = true
  }

  const zoneColor = zone === 'A' ? '#22c55e' : zone === 'B' ? '#f59e0b' : zone === 'C' ? '#ef4444' : '#666'

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className={`w-full max-w-[160px] ${className}`}
      aria-label="Position target zones"
    >
      {/* C zone — red */}
      <circle cx={CX} cy={CY} r={R_C} fill="#ef444410" stroke="#ef4444" strokeWidth={1} strokeDasharray="4 3" />

      {/* B zone — amber */}
      <circle cx={CX} cy={CY} r={R_B} fill="#f59e0b10" stroke="#f59e0b" strokeWidth={1} strokeDasharray="4 3" />

      {/* A zone — green */}
      <circle cx={CX} cy={CY} r={R_A} fill="#22c55e20" stroke="#22c55e" strokeWidth={1.5} />

      {/* Approach median line */}
      {nextShotDirection && (
        <line
          x1={CX} y1={CY}
          x2={lx2} y2={ly2}
          stroke="#facc15" strokeWidth={1.5} strokeDasharray="5 3" opacity={0.7}
        />
      )}

      {/* Centre crosshair */}
      <line x1={CX - 8} y1={CY} x2={CX + 8} y2={CY} stroke="#ffffff40" strokeWidth={1} />
      <line x1={CX} y1={CY - 8} x2={CX} y2={CY + 8} stroke="#ffffff40" strokeWidth={1} />
      <circle cx={CX} cy={CY} r={3} fill="#22c55e" />

      {/* Actual landing dot */}
      {showDot && (
        <>
          <circle cx={dotX} cy={dotY} r={6} fill={`${zoneColor}40`} />
          <circle cx={dotX} cy={dotY} r={4} fill={zoneColor} />
        </>
      )}

      {/* Zone labels */}
      <text x={CX + R_A + 4} y={CY - 3} fontSize={8} fill="#22c55e" fontFamily="monospace">A</text>
      <text x={CX + R_B + 4} y={CY - 3} fontSize={8} fill="#f59e0b" fontFamily="monospace">B</text>
      <text x={CX + R_C - 10} y={CY - 3} fontSize={8} fill="#ef4444" fontFamily="monospace">C</text>
    </svg>
  )
}
