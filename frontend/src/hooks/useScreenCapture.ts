import { useState, useRef, useCallback } from 'react';

type CaptureStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface UseScreenCaptureReturn {
  status: CaptureStatus;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  connect: () => Promise<void>;
  captureFrame: () => Promise<Blob | null>;
  disconnect: () => void;
}

export function useScreenCapture(): UseScreenCaptureReturn {
  const [status, setStatus] = useState<CaptureStatus>('disconnected');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const disconnect = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setStatus('disconnected');
  }, []);

  const connect = useCallback(async () => {
    setStatus('connecting');
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { cursor: 'always' } as MediaTrackConstraints,
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      // Auto-disconnect when user stops sharing
      const videoTrack = stream.getVideoTracks()[0];
      videoTrack.addEventListener('ended', () => {
        disconnect();
      });

      setStatus('connected');
    } catch (err) {
      if (err instanceof DOMException && err.name === 'NotAllowedError') {
        setStatus('error');
      } else {
        setStatus('error');
        throw err;
      }
    }
  }, [disconnect]);

  const captureFrame = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null;
    }

    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
    }
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0);

    return new Promise<Blob | null>((resolve) => {
      canvas.toBlob(
        (blob) => resolve(blob),
        'image/jpeg',
        0.85,
      );
    });
  }, []);

  return { status, videoRef, connect, captureFrame, disconnect };
}
