import type { GDTCallout as GDTCalloutType } from '../types';

const SYMBOL_COLORS: Record<string, string> = {
  // Form — blue
  flatness: 'text-gdt-form',
  circularity: 'text-gdt-form',
  cylindricity: 'text-gdt-form',
  straightness: 'text-gdt-form',
  // Orientation — green
  perpendicularity: 'text-gdt-orientation',
  angularity: 'text-gdt-orientation',
  parallelism: 'text-gdt-orientation',
  // Location — red
  position: 'text-gdt-location',
  concentricity: 'text-gdt-location',
  symmetry: 'text-gdt-location',
  // Profile — purple
  profile_surface: 'text-gdt-profile',
  profile_line: 'text-gdt-profile',
  // Runout — orange
  circular_runout: 'text-gdt-runout',
  total_runout: 'text-gdt-runout',
};

function getSymbolColor(symbolName: string): string {
  return SYMBOL_COLORS[symbolName] ?? 'text-surface-300';
}

function capitalizeFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
}

interface Props {
  callout: GDTCalloutType;
}

export function GDTCallout({ callout }: Props) {
  const color = getSymbolColor(callout.symbol_name);
  const datumCount = callout.datum_references.length;

  return (
    <div className="mb-5">
      <div
        className="inline-grid border-2 border-surface-200 bg-surface-950 font-mono text-lg"
        style={{
          gridTemplateColumns: `auto auto${datumCount > 0 ? ` repeat(${datumCount}, auto)` : ''}`,
        }}
      >
        {/* Symbol cell */}
        <div
          className={`px-3 py-2 border-r-2 border-surface-200 flex items-center justify-center ${color}`}
          title={callout.symbol_name}
        >
          {callout.symbol}
        </div>

        {/* Tolerance + modifier cell */}
        <div
          className={`px-3 py-2 flex items-center justify-center text-surface-100 ${datumCount > 0 ? 'border-r-2 border-surface-200' : ''}`}
        >
          {callout.tolerance_value}
          {callout.modifier_symbol && (
            <span className="ml-1">{callout.modifier_symbol}</span>
          )}
        </div>

        {/* Datum reference cells */}
        {callout.datum_references.map((datum, i) => (
          <div
            key={datum}
            className={`px-3 py-2 flex items-center justify-center text-surface-100 font-semibold ${i < datumCount - 1 ? 'border-r-2 border-surface-200' : ''}`}
          >
            {datum}
          </div>
        ))}
      </div>

      {/* Label below frame */}
      <div className="mt-1 text-sm text-surface-400">
        <span className={color}>{capitalizeFirst(callout.symbol_name)}</span>
        <span className="mx-2">|</span>
        <span>{callout.feature}</span>
      </div>
    </div>
  );
}
