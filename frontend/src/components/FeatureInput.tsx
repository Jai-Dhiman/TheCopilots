import { ScreenCapture } from './ScreenCapture';

interface Props {
  onAnalyze: (blob: Blob, description: string) => void;
  isStreaming: boolean;
}

export function FeatureInput({ onAnalyze, isStreaming }: Props) {
  return (
    <div className="flex flex-col h-full">
      <ScreenCapture onAnalyze={onAnalyze} isStreaming={isStreaming} />
    </div>
  );
}
