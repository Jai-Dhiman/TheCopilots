import type { AnalysisMetadata, AnalysisStatus } from '../types';

interface Props {
  status: AnalysisStatus;
  metadata: AnalysisMetadata | null;
}

export function StatusBar({ status, metadata }: Props) {
  return (
    <footer className="fixed bottom-0 left-0 right-0 bg-surface-800 border-t border-surface-600 px-4 py-2 flex items-center justify-between text-xs text-slate-400 font-mono z-50">
      {/* Left: model info */}
      <div>
        Gemma 3n E2B int4 + Gemma 3 270M FT
      </div>

      {/* Center: latency breakdown */}
      <div className="flex gap-3">
        {metadata ? (
          <>
            <span>Student: {metadata.student_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span>Classifier: {metadata.classifier_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span>Matcher: {metadata.matcher_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span>Worker: {metadata.worker_latency_ms}ms</span>
            <span className="text-surface-600">|</span>
            <span className="text-slate-200 font-semibold">Total: {metadata.total_latency_ms}ms</span>
          </>
        ) : (
          <span>
            {status === 'streaming' ? 'Analyzing...' : 'Ready'}
          </span>
        )}
      </div>

      {/* Right: local badge */}
      <div className="flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
        <span>Local</span>
        <span className="text-surface-600">|</span>
        <span>{metadata ? metadata.cloud_calls : 0} cloud calls</span>
      </div>
    </footer>
  );
}
