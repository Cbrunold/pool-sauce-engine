/**
 * Overlay catalog — maps engine-computed values to PoolShot asset paths.
 *
 * Assets live in /public/overlays (served at /overlays/*). Licensed from
 * PoolShot.org (lifetime license, attribution in "Who We Are").
 *
 * The engine computes exact values; this selector snaps each to the nearest
 * available asset. Heavy geometric overlays (position cones) are generated as
 * SVG instead — see ZoneCone in components, not embedded here.
 */

// Cut angles for which AimingCards exist (degrees). FullBall ≈ 0 (straight).
const CARD_ANGLES = [0, 7, 14, 22, 30, 39, 48, 60, 75]

export type CardColor = 'Red' | 'Yellow'

/** Snap an arbitrary cut angle to the nearest available card angle. */
function nearestCardAngle(cutDeg: number): number {
  const a = Math.abs(cutDeg)
  return CARD_ANGLES.reduce((best, cur) =>
    Math.abs(cur - a) < Math.abs(best - a) ? cur : best
  )
}

/**
 * Map a 9-ball id to the card's two-tone vocabulary (Blackball Red/Yellow ±
 * stripe). Beta heuristic: warm balls → Red, cool → Yellow; 9 is the stripe.
 */
export function ballToCardStyle(ballId: string): { color: CardColor; stripe: boolean } {
  const warm = new Set(['1', '3', '5', '6'])   // yellow, red, orange, maroon
  const stripe = ballId === '9'
  const color: CardColor = warm.has(ballId) || ballId === '9' ? 'Red' : 'Yellow'
  return { color, stripe }
}

/**
 * Resolve the AimingCard asset for a cut.
 *
 * @param cutDeg  signed cut angle (negative = cut left, positive = cut right)
 * @param ballId  target ball id (for color/stripe styling)
 */
export function aimingCardSrc(cutDeg: number, ballId: string): string {
  const angle = nearestCardAngle(cutDeg)
  const { color, stripe } = ballToCardStyle(ballId)
  const stripeSuffix = stripe ? 'Stripe' : ''

  if (angle === 0) {
    return `/overlays/AimingCardFullBall${color}${stripeSuffix}.png`
  }
  // Sign encodes direction: negative cut → "-NN" (left), positive → "NN" (right)
  const signed = cutDeg < 0 ? `-${angle}` : `${angle}`
  return `/overlays/AimingCard${signed}${color}${stripeSuffix}.png`
}

/** Directional arrow asset by ball-style color. */
export function arrowSrc(ballId: string, large = false): string {
  const { color } = ballToCardStyle(ballId)
  const colorName = color === 'Red' ? 'Red' : 'Yellow'
  return `/overlays/Arrow_${colorName}${large ? '_Large' : ''}.png`
}

/** Pocket target bullseye (position scoring rings 1–5). */
export function pocketTargetSrc(): string {
  return '/overlays/Target_PoolShot.png'
}

/** Stroke-length / force gauge: levels 3–6, optional left/right bias. */
export function strokeLengthSrc(level: number, bias: 'left' | 'right' | 'center' = 'center'): string {
  const lvl = Math.max(3, Math.min(6, Math.round(level)))
  const dir = bias === 'left' ? 'Left' : bias === 'right' ? 'Right' : ''
  return `/overlays/StrokeLength${dir}${lvl}.png`
}

/** Full fractional-aiming protractor wheel (reference overlay). */
export function aimingWheelSrc(): string {
  return '/overlays/papbb399x399.png'
}
