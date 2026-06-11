import { useSession } from './store/session'
import { ErrorBoundary } from './components/ErrorBoundary'
import { CaptureScreen } from './screens/CaptureScreen'
import { TableScreen } from './screens/TableScreen'
import { ShotScreen } from './screens/ShotScreen'
import { DebriefScreen } from './screens/DebriefScreen'

export default function App() {
  const screen = useSession((s) => s.screen)
  const error  = useSession((s) => s.error)
  const setError = useSession((s) => s.setError)

  return (
    <ErrorBoundary>
    <div className="max-w-sm mx-auto min-h-screen bg-[#0a0a0a] relative overflow-hidden">
      {/* Global error toast */}
      {error && (
        <div
          className="absolute top-0 left-0 right-0 z-50 bg-red-900/90 text-red-200 text-xs px-4 py-2 text-center cursor-pointer"
          onClick={() => setError(null)}
        >
          {error}
        </div>
      )}

      {screen === 'capture' && <CaptureScreen />}
      {screen === 'table'   && <TableScreen />}
      {screen === 'shot'    && <ShotScreen />}
      {screen === 'debrief' && <DebriefScreen />}
    </div>
    </ErrorBoundary>
  )
}
