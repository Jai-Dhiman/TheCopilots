import { useSSE } from './hooks/useSSE';
import { FeatureInput } from './components/FeatureInput';
import { AnalysisStream } from './components/AnalysisStream';
import { StatusBar } from './components/StatusBar';

export default function App() {
  const { state, analyze, reset } = useSSE();

  const handleAnalyze = (description: string) => {
    analyze({ description });
  };

  const isStreaming = state.status === 'connecting' || state.status === 'streaming';

  return (
    <div className="h-screen flex flex-col bg-surface-900 text-slate-200">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-surface-700">
        <div>
          <h1 className="text-xl font-bold tracking-tight">ToleranceAI</h1>
          <p className="text-xs text-slate-500">GD&T Copilot — ASME Y14.5-2018</p>
        </div>
        {state.status !== 'idle' && (
          <button
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            onClick={reset}
          >
            New Analysis
          </button>
        )}
      </header>

      {/* Two-panel main */}
      <main className="flex-1 grid grid-cols-[35%_65%] min-h-0">
        <div className="border-r border-surface-700 overflow-y-auto">
          <FeatureInput onAnalyze={handleAnalyze} isStreaming={isStreaming} />
        </div>
        <div className="overflow-y-auto">
          <AnalysisStream state={state} />
        </div>
      </main>

      {/* Status bar */}
      <StatusBar status={state.status} metadata={state.metadata} />
    </div>
  );
}
