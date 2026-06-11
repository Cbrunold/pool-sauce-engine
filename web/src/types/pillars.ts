// TypeScript types derived from pillars.schema.json

export type Pocket =
  | 'top-left' | 'top-right'
  | 'bottom-left' | 'bottom-right'
  | 'side-left' | 'side-right'

export type Zone = 'A' | 'B' | 'C'

export type Force = 'soft' | 'measured' | 'firm' | 'break'
export type Acceleration = 'decelerating' | 'controlled' | 'accelerating'

export type SpinVerdict =
  | 'clean' | 'too much' | 'not enough'
  | 'wrong axis' | 'overcooked' | 'undercooked'

export type PaceControl =
  | 'clean' | 'punchy' | 'decelerated'
  | 'floated' | 'stunned-late' | 'stunned-early'

export type CorrectSide = 'high' | 'low' | 'natural' | 'forced'

// ---- Table state ----

export interface BallState {
  id: string
  x_m: number
  y_m: number
}

export interface TableState {
  table_size_m: [number, number]
  balls: BallState[]
}

// ---- Request types ----

export interface IntentionIn {
  target_ball_id: string
  pocket: Pocket
  destination_descriptor: string
  destination_coordinates_m?: [number, number]
  destination_tolerance_m?: number
}

export interface SauceIn {
  english: string
  stroke: string
  force: Force
  acceleration: Acceleration
  recipe_rationale?: string
  speed_margin?: number
  vertical_tips?: number    // + follow / − draw  (manual override)
  horizontal_tips?: number  // + right / − left   (manual override)
}

export interface PlanRequest {
  state: TableState
  intention: IntentionIn
  sauce?: SauceIn
  cue_ball_id?: string
  shot_id?: string
  bank_rails?: number      // 0 = direct; 1/2/3 = forced bank
  optimize_sauce?: boolean // derive spin/speed for the leave
}

export interface DebriefOverridesIn {
  spin_verdict?: SpinVerdict
  spin_notes?: string
  pace_control?: PaceControl | null
  correct_side?: CorrectSide
  risk_zones_crossed?: string[]
  mastery_excellent?: string
  mastery_fragile?: string
}

export interface DebriefRequest {
  plan: PillarPlan
  actual_cue_position_m?: [number, number]
  overrides?: DebriefOverridesIn
}

// ---- Response types ----

// Full Pillar I-III (or I-V after debrief) document
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type PillarPlan = Record<string, any>

export interface PlanResponse {
  plan: PillarPlan
}

export interface DebriefResponse {
  plan: PillarPlan
}

export interface DetectedBall {
  id: string | null
  x_m: number
  y_m: number
  color_hsv: [number, number, number]
  confidence: number
  needs_confirm: boolean
  radius_px: number
}

export interface DetectResponse {
  balls: DetectedBall[]
  table_corners_px: [number, number][] | null
  width_px: number
  height_px: number
}

// ---- Ranked cue-destination options ----

export interface RankedOption {
  rank: number
  difficulty_label: 'stock' | 'comfortable' | 'tricky' | 'hard'
  difficulty: number
  makeable: boolean
  english: string
  stroke: string
  vertical_tips: number
  horizontal_tips: number
  speed_margin: number
  predicted_landing_m: [number, number]
  landing_error_m: number
}

export interface CueOptionsResponse {
  options: RankedOption[]
}

// ---- Game scope: beta is 3 balls ----

// Manual placement order — cue always last.
export const PLACEMENT_ORDER = ['8', '9', 'cue']
// Balls that can be a shot target (not the cue).
export const GAME_OBJECT_BALLS = ['8', '9']

export const NINE_BALL_SEQUENCE = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

export const BALL_COLORS: Record<string, string> = {
  cue: '#f5f5f0',
  '1':  '#f5c800',
  '2':  '#1a5fcc',
  '3':  '#d92b2b',
  '4':  '#7b2fa0',
  '5':  '#f57c00',
  '6':  '#8b1a1a',
  '7':  '#00897b',
  '8':  '#1a1a1a',
  '9':  '#f5c800', // stripe — rendered differently
}

export const POCKET_POSITIONS: Record<Pocket, [number, number]> = {
  'bottom-left':  [0,    0],
  'bottom-right': [1.27, 0],
  'side-left':    [0,    1.27],
  'side-right':   [1.27, 1.27],
  'top-left':     [0,    2.54],
  'top-right':    [1.27, 2.54],
}
