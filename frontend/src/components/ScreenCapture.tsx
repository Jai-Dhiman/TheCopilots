import { useState, useRef, useEffect } from 'react';
import { useScreenCapture } from '../hooks/useScreenCapture';

interface Props {
  onAnalyze: (blob: Blob, description: string) => void;
  isStreaming: boolean;
}

export function ScreenCapture({ onAnalyze, isStreaming }: Props) {
  const { status, videoRef, connect, captureFrame, disconnect } = useScreenCapture();
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const blobRef = useRef<Blob | null>(null);

  // Revoke preview URL on cleanup
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleCapture = async () => {
    const blob = await captureFrame();
    if (!blob) return;

    blobRef.current = blob;
    setCapturedBlob(blob);
    const url = URL.createObjectURL(blob);
    setPreviewUrl(url);
  };

  const handleRetake = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setCapturedBlob(null);
    blobRef.current = null;
  };

  const handleAnalyze = () => {
    if (!blobRef.current) return;
    onAnalyze(blobRef.current, description.trim());
  };

  const handleDisconnect = () => {
    handleRetake();
    setDescription('');
    disconnect();
  };

  // Disconnected state
  if (status === 'disconnected' || status === 'error') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
        <div className="w-16 h-16 border-2 border-surface-500 flex items-center justify-center text-surface-400">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="3" width="20" height="14" rx="0" />
            <line x1="8" y1="21" x2="16" y2="21" />
            <line x1="12" y1="17" x2="12" y2="21" />
          </svg>
        </div>
        <button
          className="px-6 py-2.5 bg-accent-500 text-surface-950 font-mono font-semibold text-sm uppercase tracking-wide hover:bg-accent-400 transition-colors"
          onClick={connect}
        >
          Connect to CAD
        </button>
        {status === 'error' && (
          <p className="text-red-400 text-xs font-mono">Screen sharing was denied or failed</p>
        )}
        <p className="text-surface-500 text-xs text-center max-w-[240px]">
          Share your FreeCAD or CAD window to capture features for analysis
        </p>
      </div>
    );
  }

  // Connecting state
  if (status === 'connecting') {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <p className="text-accent-400 font-mono text-sm indicator-pulse">
          Waiting for screen selection...
        </p>
      </div>
    );
  }

  // Connected state -- with or without captured frame
  return (
    <div className="flex flex-col h-full p-4 gap-3">
      {!capturedBlob ? (
        <>
          {/* Live video preview */}
          <div className="relative flex-1 min-h-0 bg-surface-950 border border-surface-600">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-contain"
            />
            <div className="absolute top-2 left-2 flex items-center gap-1.5 px-2 py-0.5 bg-surface-950/80">
              <span className="inline-block w-2 h-2 bg-red-500 indicator-pulse" style={{ boxShadow: '0 0 6px #EF4444' }} />
              <span className="text-red-400 text-[10px] font-mono font-semibold uppercase">LIVE</span>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              className="flex-1 py-2.5 bg-accent-500 text-surface-950 font-mono font-semibold text-sm uppercase tracking-wide hover:bg-accent-400 transition-colors"
              onClick={handleCapture}
            >
              Capture Frame
            </button>
            <button
              className="px-4 py-2.5 border border-surface-600 text-surface-400 font-mono text-sm uppercase tracking-wide hover:text-surface-200 hover:border-surface-400 transition-colors"
              onClick={handleDisconnect}
            >
              Disconnect
            </button>
          </div>
        </>
      ) : (
        <>
          {/* Frozen frame preview */}
          <div className="relative flex-1 min-h-0 bg-surface-950 border border-surface-600">
            {previewUrl && (
              <img
                src={previewUrl}
                alt="Captured frame"
                className="w-full h-full object-contain"
              />
            )}
            <div className="absolute top-2 left-2 px-2 py-0.5 bg-surface-950/80">
              <span className="text-accent-400 text-[10px] font-mono font-semibold uppercase">CAPTURED</span>
            </div>
          </div>

          {/* Optional description */}
          <textarea
            className="bg-surface-700 border border-surface-600 p-3 text-surface-200 font-mono text-sm resize-none placeholder:text-surface-500 focus:outline-none focus:border-accent-500 min-h-[60px]"
            placeholder="Optional: describe the feature..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />

          <div className="flex gap-2">
            <button
              className="px-4 py-2.5 border border-surface-600 text-surface-400 font-mono text-sm uppercase tracking-wide hover:text-surface-200 hover:border-surface-400 transition-colors"
              onClick={handleRetake}
            >
              Retake
            </button>
            <button
              className="flex-1 py-2.5 bg-accent-500 text-surface-950 font-mono font-semibold text-sm uppercase tracking-wide hover:bg-accent-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              onClick={handleAnalyze}
              disabled={isStreaming}
            >
              Capture & Analyze
            </button>
          </div>
        </>
      )}
    </div>
  );
}
