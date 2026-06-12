import { create } from 'zustand'
import type { BallState, PillarPlan, Pocket } from '../types/pillars'
import { NINE_BALL_SEQUENCE } from '../types/pillars'

export type Screen = 'capture' | 'table' | 'shot' | 'debrief'

export interface SessionState {
  // Navigation
  screen: Screen
  setScreen: (s: Screen) => void

  // Table layout
  balls: BallState[]
  setBalls: (balls: BallState[]) => void
  updateBall: (id: string, x_m: number, y_m: number) => void
  removeBall: (id: string) => void

  // 9-ball sequence
  sequence: string[]             // remaining balls in order
  currentBallId: string | null
  advanceSequence: () => void
  resetSequence: () => void

  // Shot type — 0 = direct, 1/2/3 = bank rails
  bankRails: number
  setBankRails: (n: number) => void

  // Let the engine derive spin/speed for the leave (vs default stun)
  optimizeSauce: boolean
  setOptimizeSauce: (v: boolean) => void

  // Manual spin: vertical (-5 draw .. +5 follow), side (-5 left .. +5 right)
  manualSpin: boolean
  setManualSpin: (v: boolean) => void
  spinV: number
  setSpinV: (n: number) => void
  spinH: number
  setSpinH: (n: number) => void

  // Pace: multiplier on the minimum cue speed (1.05 = just enough .. 3.0 = break)
  pace: number
  setPace: (n: number) => void

  // Cheat the pocket: aim offset in degrees (− left jaw .. + right jaw)
  cutOffset: number
  setCutOffset: (n: number) => void

  // Shot intention overrides
  selectedPocket: Pocket | null
  setSelectedPocket: (p: Pocket | null) => void
  destinationDescriptor: string
  setDestinationDescriptor: (d: string) => void
  destinationCoords: [number, number] | null
  setDestinationCoords: (c: [number, number] | null) => void

  // Current plan and debrief
  currentPlan: PillarPlan | null
  setCurrentPlan: (p: PillarPlan | null) => void
  actualCuePosition: [number, number] | null
  setActualCuePosition: (pos: [number, number] | null) => void

  // Error state
  error: string | null
  setError: (e: string | null) => void

  // Reset everything
  resetSession: () => void
}

const DEFAULT_SEQUENCE = [...NINE_BALL_SEQUENCE]

export const useSession = create<SessionState>((set, get) => ({
  screen: 'capture',
  setScreen: (screen) => set({ screen }),

  balls: [],
  setBalls: (balls) => set({ balls }),
  updateBall: (id, x_m, y_m) =>
    set((s) => ({
      balls: s.balls.map((b) => (b.id === id ? { ...b, x_m, y_m } : b)),
    })),
  removeBall: (id) =>
    set((s) => ({ balls: s.balls.filter((b) => b.id !== id) })),

  sequence: DEFAULT_SEQUENCE,
  currentBallId: DEFAULT_SEQUENCE[0],
  advanceSequence: () =>
    set((s) => {
      const next = s.sequence.slice(1)
      return { sequence: next, currentBallId: next[0] ?? null }
    }),
  resetSequence: () =>
    set({ sequence: DEFAULT_SEQUENCE, currentBallId: DEFAULT_SEQUENCE[0] }),

  bankRails: 0,
  setBankRails: (bankRails) => set({ bankRails }),

  optimizeSauce: true,
  setOptimizeSauce: (optimizeSauce) => set({ optimizeSauce }),

  manualSpin: false,
  setManualSpin: (manualSpin) => set({ manualSpin }),
  spinV: 0,
  setSpinV: (spinV) => set({ spinV: Math.max(-5, Math.min(5, spinV)) }),
  spinH: 0,
  setSpinH: (spinH) => set({ spinH: Math.max(-5, Math.min(5, spinH)) }),

  pace: 1.8,
  setPace: (pace) => set({ pace: Math.max(1.05, Math.min(3.0, pace)) }),

  cutOffset: 0,
  setCutOffset: (cutOffset) => set({ cutOffset: Math.max(-10, Math.min(10, cutOffset)) }),

  selectedPocket: null,
  setSelectedPocket: (selectedPocket) => set({ selectedPocket }),
  destinationDescriptor: 'center table for next shot',
  setDestinationDescriptor: (destinationDescriptor) => set({ destinationDescriptor }),
  destinationCoords: null,
  setDestinationCoords: (destinationCoords) => set({ destinationCoords }),

  currentPlan: null,
  setCurrentPlan: (currentPlan) => set({ currentPlan }),
  actualCuePosition: null,
  setActualCuePosition: (actualCuePosition) => set({ actualCuePosition }),

  error: null,
  setError: (error) => set({ error }),

  resetSession: () =>
    set({
      screen: 'capture',
      balls: [],
      sequence: DEFAULT_SEQUENCE,
      currentBallId: DEFAULT_SEQUENCE[0],
      selectedPocket: null,
      destinationDescriptor: 'center table for next shot',
      destinationCoords: null,
      currentPlan: null,
      actualCuePosition: null,
      bankRails: 0,
      optimizeSauce: true,
      manualSpin: false,
      spinV: 0,
      spinH: 0,
      pace: 1.8,
      cutOffset: 0,
      error: null,
    }),
}))

// Dev-only: expose the store for debugging in the preview console.
if (import.meta.env.DEV) {
  ;(window as unknown as { __session?: typeof useSession }).__session = useSession
}
