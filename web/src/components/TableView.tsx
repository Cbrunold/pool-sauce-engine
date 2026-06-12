/**
 * TableView — 2D SVG top-down pool table.
 *
 * Renders the table felt, six pockets, all balls, and optional overlays
 * (aim line, escape route, destination zone). Supports draggable balls
 * for the confirm/correct workflow.
 */

import React, { useCallback, useRef, useState } from 'react'
import type { BallState, Pocket } from '../types/pillars'
import { BALL_COLORS, POCKET_POSITIONS } from '../types/pillars'

// Physical table: 2.54m × 1.27m  →  rendered portrait (height > width)
const TABLE_LENGTH_M = 2.54
const TABLE_WIDTH_M  = 1.27
const POCKET_R_M     = 0.065

interface Props {
  balls: BallState[]
  currentBallId?: string | null
  aimLine?: { from: [number, number]; to: [number, number] }
  escapeRoute?: [number, number][]
  destinationZone?: { center: [number, number]; radius_m: number }
  landingCone?: {
    apex: [number, number]
    direction: [number, number]   // table-space vector the cone points along
    halfAngleDeg: number
    lengthM: number
    color: string
  }
  bankPath?: [number, number][]   // object-ball zig-zag (start, rails…, pocket)
  objectBallPath?: [number, number][]   // direct object-ball path → pocket
  selectedPocket?: Pocket | null
  onBallMove?: (id: string, x_m: number, y_m: number) => void
  onTableTap?: (x_m: number, y_m: number) => void
  onPocketSelect?: (pocket: Pocket) => void
  highlightBalls?: string[]
  className?: string
}

export function TableView({
  balls,
  currentBallId,
  aimLine,
  escapeRoute,
  destinationZone,
  landingCone,
  bankPath,
  objectBallPath,
  selectedPocket,
  onBallMove,
  onTableTap,
  onPocketSelect,
  highlightBalls = [],
  className = '',
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  // SVG viewport: render table portrait with padding
  const PAD = 20
  const SVG_H = 520
  const SVG_W = Math.round(SVG_H * (TABLE_WIDTH_M / TABLE_LENGTH_M)) + PAD * 2
  const FELT_H = SVG_H - PAD * 2
  const FELT_W = Math.round(FELT_H * (TABLE_WIDTH_M / TABLE_LENGTH_M))
  const FELT_X = (SVG_W - FELT_W) / 2
  const FELT_Y = PAD

  const toSvg = useCallback((x_m: number, y_m: number): [number, number] => {
    const sx = FELT_X + (x_m / TABLE_WIDTH_M) * FELT_W
    // y_m origin is bottom-left; SVG origin is top-left
    const sy = FELT_Y + FELT_H - (y_m / TABLE_LENGTH_M) * FELT_H
    return [sx, sy]
  }, [FELT_X, FELT_W, FELT_H, FELT_Y])

  const fromSvg = useCallback((sx: number, sy: number): [number, number] => {
    const x_m = ((sx - FELT_X) / FELT_W) * TABLE_WIDTH_M
    const y_m = ((FELT_Y + FELT_H - sy) / FELT_H) * TABLE_LENGTH_M
    return [
      Math.max(0, Math.min(TABLE_WIDTH_M, x_m)),
      Math.max(0, Math.min(TABLE_LENGTH_M, y_m)),
    ]
  }, [FELT_X, FELT_W, FELT_H, FELT_Y])

  // Balls are drawn larger than physical scale for legibility on a phone —
  // a real 57 mm ball on a 9-ft table is too small to read or tap. Positions
  // stay exact; only the rendered radius is exaggerated.
  const BALL_VISUAL_SCALE = 1.9
  const BALL_R_SVG = (0.028575 / TABLE_WIDTH_M) * FELT_W * BALL_VISUAL_SCALE

  // Dragging state
  const dragRef = useRef<{ id: string } | null>(null)

  const handleSvgMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!dragRef.current || !svgRef.current || !onBallMove) return
    const rect = svgRef.current.getBoundingClientRect()
    const sx = (e.clientX - rect.left) * (SVG_W / rect.width)
    const sy = (e.clientY - rect.top) * (SVG_H / rect.height)
    const [x_m, y_m] = fromSvg(sx, sy)
    onBallMove(dragRef.current.id, x_m, y_m)
  }, [fromSvg, onBallMove, SVG_W, SVG_H])

  const handleSvgTouchMove = useCallback((e: React.TouchEvent<SVGSVGElement>) => {
    if (!dragRef.current || !svgRef.current || !onBallMove) return
    e.preventDefault()
    const t = e.touches[0]
    const rect = svgRef.current.getBoundingClientRect()
    const sx = (t.clientX - rect.left) * (SVG_W / rect.width)
    const sy = (t.clientY - rect.top) * (SVG_H / rect.height)
    const [x_m, y_m] = fromSvg(sx, sy)
    onBallMove(dragRef.current.id, x_m, y_m)
  }, [fromSvg, onBallMove, SVG_W, SVG_H])

  const stopDrag = useCallback(() => { dragRef.current = null }, [])

  const handleFeltTap = useCallback((e: React.MouseEvent<SVGRectElement>) => {
    if (!onTableTap || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const sx = (e.clientX - rect.left) * (SVG_W / rect.width)
    const sy = (e.clientY - rect.top) * (SVG_H / rect.height)
    onTableTap(...fromSvg(sx, sy))
  }, [fromSvg, onTableTap, SVG_W, SVG_H])

  const pocketRadius = (POCKET_R_M / TABLE_WIDTH_M) * FELT_W

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${SVG_W} ${SVG_H}`}
      className={`w-full select-none touch-none ${className}`}
      onMouseMove={handleSvgMouseMove}
      onMouseUp={stopDrag}
      onMouseLeave={stopDrag}
      onTouchMove={handleSvgTouchMove}
      onTouchEnd={stopDrag}
    >
      {/* Rail / border */}
      <rect
        x={FELT_X - 12} y={FELT_Y - 12}
        width={FELT_W + 24} height={FELT_H + 24}
        rx={6} fill="#2a1a0a" stroke="#4a3010" strokeWidth={2}
      />

      {/* Rail diamonds — long rails by eighths (skip side pocket), short
          rails by quarters. The standard sight markers for reading the table. */}
      {(() => {
        const r = 3.4
        const off = 6  // center of the rail strip, outside the felt edge
        const diamond = (cx: number, cy: number, key: string) => (
          <polygon
            key={key}
            points={`${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`}
            fill="#e7d9b0"
            opacity={0.9}
          />
        )
        const out: React.ReactNode[] = []
        // Long rails: 1/8 … 7/8 of length, skipping 4/8 (the side pocket).
        for (const n of [1, 2, 3, 5, 6, 7]) {
          const sy = FELT_Y + FELT_H - (n / 8) * FELT_H
          out.push(diamond(FELT_X - off, sy, `L${n}`))
          out.push(diamond(FELT_X + FELT_W + off, sy, `R${n}`))
        }
        // Short rails: quarters of width.
        for (const n of [1, 2, 3]) {
          const sx = FELT_X + (n / 4) * FELT_W
          out.push(diamond(sx, FELT_Y - off, `T${n}`))
          out.push(diamond(sx, FELT_Y + FELT_H + off, `B${n}`))
        }
        return <g>{out}</g>
      })()}

      {/* Felt */}
      <rect
        x={FELT_X} y={FELT_Y}
        width={FELT_W} height={FELT_H}
        fill="#0e5c2a"
        onClick={handleFeltTap}
        style={{ cursor: onTableTap ? 'crosshair' : 'default' }}
      />

      {/* Landing cone — position window, drawn behind balls */}
      {landingCone && (() => {
        const { apex, direction, halfAngleDeg, lengthM, color } = landingCone
        const mag = Math.hypot(direction[0], direction[1]) || 1
        const ux = direction[0] / mag
        const uy = direction[1] / mag
        const half = (halfAngleDeg * Math.PI) / 180

        // Sample the arc edge in table coords, rotating the unit vector
        const STEPS = 14
        const arcPts: [number, number][] = []
        for (let i = 0; i <= STEPS; i++) {
          const t = -half + (2 * half * i) / STEPS
          const cos = Math.cos(t)
          const sin = Math.sin(t)
          const rx = ux * cos - uy * sin
          const ry = ux * sin + uy * cos
          arcPts.push([apex[0] + rx * lengthM, apex[1] + ry * lengthM])
        }

        const apexSvg = toSvg(apex[0], apex[1])
        const arcSvg = arcPts.map((p) => toSvg(p[0], p[1]))
        const path = [
          `M ${apexSvg[0]} ${apexSvg[1]}`,
          ...arcSvg.map(([x, y]) => `L ${x} ${y}`),
          'Z',
        ].join(' ')

        // Median line apex → tip
        const tip = toSvg(apex[0] + ux * lengthM, apex[1] + uy * lengthM)

        return (
          <g opacity={0.85}>
            <path d={path} fill={color} fillOpacity={0.28} stroke={color} strokeWidth={1} strokeOpacity={0.6} />
            <line x1={apexSvg[0]} y1={apexSvg[1]} x2={tip[0]} y2={tip[1]}
              stroke={color} strokeWidth={1.25} strokeDasharray="5 3" opacity={0.85} />
          </g>
        )
      })()}

      {/* Object-ball path → pocket (direct shots): solid amber, the ball you pot */}
      {objectBallPath && objectBallPath.length > 1 && (() => {
        const pts = objectBallPath.map(([x, y]) => toSvg(x, y).join(',')).join(' ')
        return (
          <polyline points={pts}
            fill="none" stroke="#facc15" strokeWidth={2.5} opacity={0.85}
            strokeLinecap="round" />
        )
      })()}

      {/* Cue-ball path — dotted white. Pre-contact (aim) + post-contact (escape). */}
      {aimLine && (() => {
        const [x1, y1] = toSvg(...aimLine.from)
        const [x2, y2] = toSvg(...aimLine.to)
        return (
          <line x1={x1} y1={y1} x2={x2} y2={y2}
            stroke="#f1f5f9" strokeWidth={1.5} strokeDasharray="2 4"
            strokeLinecap="round" opacity={0.9} />
        )
      })()}
      {escapeRoute && escapeRoute.length > 1 && (() => {
        const pts = escapeRoute.map(([x, y]) => toSvg(x, y).join(',')).join(' ')
        return (
          <polyline points={pts}
            fill="none" stroke="#f1f5f9" strokeWidth={1.5}
            strokeDasharray="2 4" strokeLinecap="round" opacity={0.9} />
        )
      })()}

      {/* Bank path — object ball zig-zag off the rails */}
      {bankPath && bankPath.length > 1 && (() => {
        const pts = bankPath.map(([x, y]) => toSvg(x, y))
        const poly = pts.map(([x, y]) => `${x},${y}`).join(' ')
        return (
          <g>
            <polyline points={poly} fill="none" stroke="#f97316" strokeWidth={2}
              strokeDasharray="7 4" opacity={0.9} strokeLinejoin="round" />
            {/* Rail contact dots (interior vertices) */}
            {pts.slice(1, -1).map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r={3.5} fill="#f97316" />
            ))}
          </g>
        )
      })()}

      {/* Destination zone */}
      {destinationZone && (() => {
        const [cx, cy] = toSvg(...destinationZone.center)
        const r = (destinationZone.radius_m / TABLE_WIDTH_M) * FELT_W
        return (
          <>
            <circle cx={cx} cy={cy} r={r * 3} fill="none" stroke="#ef4444" strokeWidth={1} opacity={0.35} strokeDasharray="3 3" />
            <circle cx={cx} cy={cy} r={r * 2} fill="none" stroke="#f59e0b" strokeWidth={1} opacity={0.45} strokeDasharray="3 3" />
            <circle cx={cx} cy={cy} r={r}     fill="rgba(34,197,94,0.15)" stroke="#22c55e" strokeWidth={1.5} opacity={0.7} />
            {/* Crosshair */}
            <line x1={cx - r * 1.4} y1={cy} x2={cx + r * 1.4} y2={cy} stroke="#22c55e" strokeWidth={1} opacity={0.6} />
            <line x1={cx} y1={cy - r * 1.4} x2={cx} y2={cy + r * 1.4} stroke="#22c55e" strokeWidth={1} opacity={0.6} />
          </>
        )
      })()}

      {/* Pockets */}
      {(Object.entries(POCKET_POSITIONS) as [Pocket, [number, number]][]).map(([name, [px, py]]) => {
        const [sx, sy] = toSvg(px, py)
        const isSelected = selectedPocket === name
        return (
          <circle
            key={name}
            cx={sx} cy={sy} r={pocketRadius}
            fill={isSelected ? '#facc15' : '#0a0a0a'}
            stroke={isSelected ? '#fde68a' : '#1a1a1a'}
            strokeWidth={isSelected ? 2 : 1}
            style={{ cursor: onPocketSelect ? 'pointer' : 'default' }}
            onClick={() => onPocketSelect?.(name)}
          />
        )
      })}

      {/* Balls */}
      {balls.map((ball) => {
        const [sx, sy] = toSvg(ball.x_m, ball.y_m)
        const isCurrent = ball.id === currentBallId
        const isHighlighted = highlightBalls.includes(ball.id)
        const color = BALL_COLORS[ball.id] ?? '#888'
        const isStripe = ball.id === '9'
        const isCue = ball.id === 'cue'

        return (
          <g key={ball.id}
            onMouseDown={() => { if (onBallMove) dragRef.current = { id: ball.id } }}
            onTouchStart={() => { if (onBallMove) dragRef.current = { id: ball.id } }}
            style={{ cursor: onBallMove ? 'grab' : 'default' }}
          >
            {/* Selection ring */}
            {(isCurrent || isHighlighted) && (
              <circle cx={sx} cy={sy} r={BALL_R_SVG + 3.5}
                fill="none" stroke="#facc15" strokeWidth={2} opacity={0.9} />
            )}

            {/* Ball body */}
            <circle cx={sx} cy={sy} r={BALL_R_SVG}
              fill={color}
              stroke={isCue ? '#ccc' : '#0a0a0a'}
              strokeWidth={0.8}
            />

            {/* Stripe for 9-ball */}
            {isStripe && (
              <rect
                x={sx - BALL_R_SVG} y={sy - BALL_R_SVG * 0.35}
                width={BALL_R_SVG * 2} height={BALL_R_SVG * 0.7}
                fill="#f5f5f0" opacity={0.85}
                clipPath={`circle(${BALL_R_SVG}px at ${sx}px ${sy}px)`}
              />
            )}

            {/* Ball number */}
            {!isCue && (
              <text
                x={sx} y={sy + BALL_R_SVG * 0.4}
                textAnchor="middle"
                fontSize={BALL_R_SVG * 1.1}
                fontWeight="bold"
                fill={['1','2','3','4','5','6','7','8','9'].includes(ball.id) ? '#fff' : '#000'}
                style={{ pointerEvents: 'none', userSelect: 'none' }}
              >
                {ball.id}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}
