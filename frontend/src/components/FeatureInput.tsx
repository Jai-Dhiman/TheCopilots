import { useState } from 'react';
import { ScreenCapture } from './ScreenCapture';

const PRESETS: { label: string; description: string }[] = [
  {
    label: 'Perpendicular Boss',
    description: 'Cylindrical aluminum boss, 12mm diameter, needs to be perpendicular to the mounting face within 0.05mm. CNC machined, mates with a bearing bore.',
  },
  {
    label: 'Hole Pattern',
    description: '4x M6 threaded holes on a bolt circle, 50mm PCD, need to line up with a mating flange. Sheet metal part, laser cut then tapped.',
  },
  {
    label: 'Flat Surface',
    description: 'Cast iron base plate, 300mm x 200mm, needs to be flat within 0.1mm. This is the primary mounting surface for the assembly.',
  },
  {
    label: 'Shaft',
    description: 'Turned steel shaft with two bearing journals, 25mm diameter, spaced 100mm apart. Journals need to be concentric within 0.02mm. Lathe turned.',
  },
];

type TabId = 'text' | 'capture';

interface Props {
  onAnalyze: (description: string, imageBlob?: Blob) => void;
  isStreaming: boolean;
}

export function FeatureInput({ onAnalyze, isStreaming }: Props) {
  const [description, setDescription] = useState('');
  const [activeTab, setActiveTab] = useState<TabId>('text');

  const handleSubmit = () => {
    const text = description.trim();
    if (!text) return;
    onAnalyze(text);
  };

  const handleCaptureAnalyze = (blob: Blob, captureDescription: string) => {
    onAnalyze(captureDescription || 'Analyze the captured CAD feature', blob);
  };

  const tabs: { id: TabId; label: string }[] = [
    { id: 'text', label: 'TEXT' },
    { id: 'capture', label: 'CAD CAPTURE' },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-surface-700">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`flex-1 py-2.5 text-xs font-mono font-semibold uppercase tracking-wide transition-colors ${
              activeTab === tab.id
                ? 'text-accent-400 border-b-2 border-accent-500'
                : 'text-surface-500 hover:text-surface-300'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'text' ? (
        <div className="flex flex-col flex-1 p-6 gap-4">
          <h2 className="text-lg font-semibold text-surface-200 font-mono">Feature Description</h2>

          <textarea
            className="flex-1 bg-surface-700 border border-surface-600 p-4 text-surface-200 font-mono text-sm resize-none placeholder:text-surface-500 focus:outline-none focus:border-accent-500 min-h-[160px]"
            placeholder="Describe your part feature..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit();
            }}
          />

          {/* Preset buttons */}
          <div>
            <p className="text-xs text-surface-500 mb-2 font-mono">Quick examples:</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  className="px-3 py-1.5 text-xs bg-surface-700 border border-surface-600 text-surface-400 hover:text-surface-200 hover:border-accent-500 transition-colors font-mono"
                  onClick={() => setDescription(preset.description)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <button
            className="w-full py-3 font-semibold transition-colors bg-accent-500 text-surface-950 hover:bg-accent-400 disabled:opacity-40 disabled:cursor-not-allowed font-mono uppercase tracking-wide"
            onClick={handleSubmit}
            disabled={isStreaming || !description.trim()}
          >
            {isStreaming ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      ) : (
        <div className="flex-1 min-h-0">
          <ScreenCapture onAnalyze={handleCaptureAnalyze} isStreaming={isStreaming} />
        </div>
      )}
    </div>
  );
}
