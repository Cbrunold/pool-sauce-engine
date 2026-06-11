/**
 * AngleDiagram — top-down aim line overlay, zoomed to the shot geometry.
 *
 * Shows cue ball → ghost ball → pocket line plus the escape route.
 * Extracted from the Pillar II data in the plan.
 */

import { TableView } from './TableView'
import type { BallState, Pocket } from '../types/pillars'

interface Props {
  plan: Record<string, unknown>
  balls: BallState[]
  className?: string
}

function extractAimLine(plan: Record<string, unknown>) {
  try {
    const p2 = plan.pillar_II as Record<string, unknown>
    const loa = p2?.line_of_aim as Record<string, unknown>
    // vector is [cueX, cueY, ghostX, ghostY]
    const v = loa?.vector as number[]
    if (!v || v.length < 4) return undefined
    const [cx, cy, gx, gy] = v
    // Extend the aim line past the ghost ball toward the target line
    const dx = gx - cx
    const dy = gy - cy
    return {
      from: [cx, cy] as [number, number],
      to: [cx + dx * 1.25, cy + dy * 1.25] as [number, number],
    }
  } catch {
    return undefined
  }
}

function extractEscapeRoute(plan: Record<string, unknown>): [number, number][] | undefined {
  try {
    const p2 = plan.pillar_II as Record<string, unknown>
    const route = p2?.escape_route as Record<string, unknown>
    const pts = route?.path_points_m as [number, number][]
    if (!pts?.length) return undefined
    return pts.map((p) => [p[0], p[1]])
  } catch {
    return undefined
  }
}

function extractDestination(plan: Record<string, unknown>) {
  try {
    const p1 = plan.pillar_I as Record<string, unknown>
    const dest = p1?.destination as Record<string, unknown>
    const coords = dest?.coordinates_m as number[]   // [x_m, y_m]
    const tol = (dest?.tolerance_m as number) ?? 0.15
    if (!coords || coords.length < 2) return undefined
    return { center: [coords[0], coords[1]] as [number, number], radius_m: tol }
  } catch {
    return undefined
  }
}

function extractPocket(plan: Record<string, unknown>): Pocket | null {
  try {
    const p1 = plan.pillar_I as Record<string, unknown>
    return (p1?.pocket as Pocket) ?? null
  } catch {
    return null
  }
}

/** Position landing cone: fans from the destination along the cue's approach. */
function extractLandingCone(
  plan: Record<string, unknown>,
  destination: { center: [number, number]; radius_m: number } | undefined,
  escapeRoute: [number, number][] | undefined,
  targetId: string | undefined,
) {
  if (!escapeRoute || escapeRoute.length < 2) return undefined
  const last = escapeRoute[escapeRoute.length - 1]
  const prev = escapeRoute[escapeRoute.length - 2]
  // Approach direction: where the cue is heading as it arrives
  const dir: [number, number] = [last[0] - prev[0], last[1] - prev[1]]
  if (Math.hypot(dir[0], dir[1]) < 1e-6) return undefined
  const apex = destination?.center ?? last
  // Fixed cyan — the cone marks the cue's *approach corridor*, independent of
  // which ball is being potted. (Ball-color tinting made the 8's cone grey.)
  return { apex, direction: dir, halfAngleDeg: 18, lengthM: 0.45, color: '#38bdf8' }
}

export function AngleDiagram({ plan, balls, className = '' }: Props) {
  const aimLine = extractAimLine(plan)
  const escapeRoute = extractEscapeRoute(plan)
  const destinationZone = extractDestination(plan)
  const pocket = extractPocket(plan)

  const p1 = plan.pillar_I as Record<string, unknown>
  const targetId = p1?.target as string | undefined   // target is a plain id string
  const highlightBalls = targetId ? [targetId] : []
  const landingCone = extractLandingCone(plan, destinationZone, escapeRoute, targetId)

  // Bank shot: the object ball's zig-zag path off the rails.
  let bankPath: [number, number][] | undefined
  try {
    const p2 = plan.pillar_II as Record<string, unknown>
    const bank = p2?.bank as Record<string, unknown> | undefined
    const pts = bank?.ob_path_points_m as [number, number][] | undefined
    if (pts?.length) bankPath = pts.map((p) => [p[0], p[1]])
  } catch { /* no bank */ }

  return (
    <TableView
      balls={balls}
      currentBallId={targetId}
      aimLine={aimLine}
      escapeRoute={escapeRoute}
      destinationZone={destinationZone}
      landingCone={landingCone}
      bankPath={bankPath}
      selectedPocket={pocket}
      highlightBalls={highlightBalls}
      className={className}
    />
  )
}
