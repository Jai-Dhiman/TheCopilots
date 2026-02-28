import { useState } from 'react';

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

interface Props {
  onAnalyze: (description: string) => void;
  isStreaming: boolean;
}

export function FeatureInput({ onAnalyze, isStreaming }: Props) {
  const [description, setDescription] = useState('');

  const handleSubmit = () => {
    const text = description.trim();
    if (!text) return;
    onAnalyze(text);
  };

  return (
    <div className="flex flex-col h-full p-6 gap-4">
      <h2 className="text-lg font-semibold text-slate-200">Feature Description</h2>

      <textarea
        className="flex-1 bg-surface-700 border border-surface-600 rounded-lg p-4 text-slate-200 font-mono text-sm resize-none placeholder:text-slate-500 focus:outline-none focus:border-slate-400 min-h-[160px]"
        placeholder="Describe your part feature..."
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit();
        }}
      />

      {/* Preset buttons */}
      <div>
        <p className="text-xs text-slate-500 mb-2">Quick examples:</p>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              className="px-3 py-1.5 text-xs bg-surface-700 border border-surface-600 rounded-md text-slate-400 hover:text-slate-200 hover:border-slate-400 transition-colors"
              onClick={() => setDescription(preset.description)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <button
        className="w-full py-3 rounded-lg font-semibold transition-colors bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
        onClick={handleSubmit}
        disabled={isStreaming || !description.trim()}
      >
        {isStreaming ? 'Analyzing...' : 'Analyze'}
      </button>
    </div>
  );
}
