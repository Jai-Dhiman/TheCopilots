import { useState, useRef, useEffect } from 'react';

const DEMO_DESCRIPTION =
  'Table made up of a rectangular surface and 4 legs that are press fit at each corner.';

async function grabScreenshot(): Promise<Blob | null> {
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: { cursor: 'always' } as MediaTrackConstraints,
    audio: false,
  });

  const video = document.createElement('video');
  video.srcObject = stream;
  video.autoplay = true;
  video.playsInline = true;

  await new Promise<void>((resolve) => {
    video.onloadeddata = () => resolve();
  });

  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    stream.getTracks().forEach((t) => t.stop());
    return null;
  }

  ctx.drawImage(video, 0, 0);
  stream.getTracks().forEach((t) => t.stop());

  return new Promise<Blob | null>((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.85);
  });
}

interface Props {
  onAnalyze: (blob: Blob, description: string) => void;
  isStreaming: boolean;
}

export function ScreenCapture({ onAnalyze, isStreaming }: Props) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const blobRef = useRef<Blob | null>(null);

  // Revoke preview URL on cleanup
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleScreenshot = async () => {
    setCapturing(true);
    setError(null);
    try {
      const blob = await grabScreenshot();
      if (!blob) {
        setError('Failed to capture screenshot');
        setCapturing(false);
        return;
      }
      blobRef.current = blob;
      setPreviewUrl(URL.createObjectURL(blob));
      setCapturing(false);
      onAnalyze(blob, DEMO_DESCRIPTION);
    } catch (err) {
      setCapturing(false);
      if (err instanceof DOMException && err.name === 'NotAllowedError') {
        setError('Screen sharing was denied');
      } else {
        setError('Screenshot failed');
      }
    }
  };

  const handleRetake = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    blobRef.current = null;
    setError(null);
  };

  const handleAnalyze = () => {
    if (!blobRef.current) return;
    onAnalyze(blobRef.current, DEMO_DESCRIPTION);
  };

  // Captured -- show screenshot
  if (previewUrl) {
    return (
      <div className="flex flex-col h-full p-4 gap-3">
        <div className="relative flex-1 min-h-0 bg-surface-950 border border-surface-600 overflow-hidden">
          <img
            src={previewUrl}
            alt="Captured screenshot"
            className="absolute inset-0 w-full h-full object-contain"
          />
          <div className="absolute top-2 left-2 px-2 py-0.5 bg-surface-950/80">
            <span className="text-accent-400 text-[10px] font-mono font-semibold uppercase">CAPTURED</span>
          </div>
        </div>
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
            {isStreaming ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>
    );
  }

  // Default -- take screenshot
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
        className="px-6 py-2.5 bg-accent-500 text-surface-950 font-mono font-semibold text-sm uppercase tracking-wide hover:bg-accent-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        onClick={handleScreenshot}
        disabled={capturing}
      >
        {capturing ? 'Capturing...' : 'Take Screenshot'}
      </button>
      {error && (
        <p className="text-red-400 text-xs font-mono">{error}</p>
      )}
      <p className="text-surface-500 text-xs text-center max-w-[240px]">
        Select your FreeCAD or CAD window to capture for analysis
      </p>
    </div>
  );
}
