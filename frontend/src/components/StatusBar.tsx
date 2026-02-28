import type { AnalysisMetadata, AnalysisStatus, CADContext } from '../types';

function StatusIndicator({ color, pulse = false }: { color: string; pulse?: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 ${pulse ? 'indicator-pulse' : ''}`}
      style={{
        backgroundColor: color,
        boxShadow: `0 0 6px ${color}`,
      }}
    />
  );
}

interface Props {
  status: AnalysisStatus;
  metadata: AnalysisMetadata | null;
  cadContext: CADContext | null;
  currentStepMessage: string | null;
}

export function StatusBar({ status, metadata, cadContext, currentStepMessage }: Props) {
  const isProcessing = status === 'streaming' || status === 'connecting';

  return (
    <footer className="fixed bottom-0 left-0 right-0 bg-surface-950 border-t border-surface-600 px-4 py-2 flex items-center justify-between text-[11px] text-surface-400 font-mono tracking-wide z-50">
      {/* Left: model info + status */}
      <div className="flex items-center gap-3">
        <StatusIndicator
          color={isProcessing ? '#FBBF24' : '#22C55E'}
          pulse={isProcessing}
        />
        <span className="text-surface-300 uppercase">
          {isProcessing ? (currentStepMessage ?? 'PROCESSING...') : 'READY'}
        </span>
        <span className="text-surface-600">|</span>
        <span>Gemma 3n E4B int4 (mlx-vlm)</span>
        <span className="text-surface-600">+</span>
        <span>Gemma 3 270M FT</span>
        <span className="text-surface-600">|</span>
        <StatusIndicator color={cadContext?.connected ? '#22C55E' : '#6B7280'} />
        <span className={cadContext?.connected ? 'text-surface-300' : 'text-surface-500'}>
          FreeCAD: {cadContext?.connected ? 'Connected' : 'Not detected'}
        </span>
      </div>

      {/* Center: latency breakdown */}
      <div className="flex gap-2">
        {metadata ? (
          <>
            <span>STU:{metadata.student_latency_ms}ms</span>
            <span className="text-surface-600">/</span>
            <span>CLS:{metadata.classifier_latency_ms}ms</span>
            <span className="text-surface-600">/</span>
            <span>MAT:{metadata.matcher_latency_ms}ms</span>
            <span className="text-surface-600">/</span>
            <span>WRK:{metadata.worker_latency_ms}ms</span>
            <span className="text-surface-600">=</span>
            <span className="text-accent-400 font-semibold">{metadata.total_latency_ms}ms</span>
          </>
        ) : (
          <span className="text-surface-500">--</span>
        )}
      </div>

      {/* Right: local + ITAR badge */}
      <div className="flex items-center gap-3">
        <StatusIndicator color="#22C55E" />
        <span>LOCAL</span>
        <span className="text-surface-600">|</span>
        <span>{metadata ? metadata.cloud_calls : 0} CLOUD</span>
        <span className="text-surface-600">|</span>
        <span className="text-accent-400 font-semibold">ITAR SAFE</span>
      </div>
    </footer>
  );
}
