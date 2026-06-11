/**
 * ErrorBoundary — catches render-time errors so a thrown component shows a
 * recoverable message instead of a blank screen. Critical on mobile, where
 * there's no console to inspect a white-screen crash.
 */

import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  reset = () => {
    this.setState({ error: null })
    // Hard reload clears any corrupted in-memory state.
    location.reload()
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white px-6 gap-4 text-center">
          <p className="text-[#facc15] tracking-widest text-sm font-bold">SOMETHING BROKE</p>
          <p className="text-gray-400 text-xs max-w-xs break-words">
            {this.state.error.message || 'An unexpected error occurred.'}
          </p>
          <button
            onClick={this.reset}
            className="mt-2 px-6 py-3 rounded border border-[#facc15] text-[#facc15] tracking-widest text-sm"
          >
            RESTART
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
