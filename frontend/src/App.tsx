import { useSSE } from './hooks/useSSE';
import { FeatureInput } from './components/FeatureInput';
import { AnalysisStream } from './components/AnalysisStream';
import { StatusBar } from './components/StatusBar';

export default function App() {
  const { state, analyze, reset } = useSSE();

  const handleAnalyze = (description: string, imageBlob?: Blob) => {
    analyze({ description }, imageBlob);
  };

  const isStreaming = state.status === 'connecting' || state.status === 'streaming';

  return (
    <div className="h-screen flex flex-col bg-surface-900 text-surface-200 font-sans">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 bg-surface-800 border-b border-surface-700">
        <div className="flex items-center gap-3">
          <div className="w-1 h-8 bg-accent-500" />
          <div>
            <h1 className="text-xl font-bold tracking-tight font-mono text-surface-100 uppercase">ToleranceAI</h1>
            <p className="text-xs text-surface-400 font-mono tracking-wide uppercase">GD&T Copilot -- ASME Y14.5-2018</p>
          </div>
        </div>
        {state.status !== 'idle' && (
          <button
            className="text-xs text-surface-500 hover:text-accent-400 transition-colors font-mono uppercase tracking-wide"
            onClick={reset}
          >
            New Analysis
          </button>
        )}
      </header>

      {/* Two-panel main */}
      <main className="flex-1 grid grid-cols-[35%_65%] min-h-0">
        <div className="bg-surface-800 border-r border-surface-700 overflow-y-auto">
          <FeatureInput onAnalyze={handleAnalyze} isStreaming={isStreaming} />
        </div>
        <div className="overflow-y-auto">
          <AnalysisStream state={state} />
        </div>
      </main>

      {/* Status bar */}
      <StatusBar status={state.status} metadata={state.metadata} cadContext={state.cadContext} currentStepMessage={state.currentStepMessage} />
    </div>
  );
}
