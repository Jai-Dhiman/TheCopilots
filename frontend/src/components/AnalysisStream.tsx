import { useState, type ReactNode } from 'react';
import type { AnalysisState, CADContext } from '../types';
import { GDTCallout } from './GDTCallout';

interface Props {
  state: AnalysisState;
}

const SHIMMER_WIDTHS = [85, 72, 95, 78, 90];

function Shimmer({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-4 bg-surface-700 animate-pulse"
          style={{ width: `${SHIMMER_WIDTHS[i % SHIMMER_WIDTHS.length]}%` }}
        />
      ))}
    </div>
  );
}

function Section({
  title,
  show,
  children,
  pending,
}: {
  title: string;
  show: boolean;
  children: ReactNode;
  pending: boolean;
}) {
  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-surface-400 font-mono uppercase tracking-wider mb-3">
        {title}
      </h3>
      <div
        className="transition-opacity duration-300"
        style={{ opacity: show ? 1 : pending ? 0.5 : 0 }}
      >
        {show ? children : pending ? <Shimmer /> : null}
      </div>
    </div>
  );
}

function CADContextPanel({ cadContext }: { cadContext: CADContext }) {
  const [expanded, setExpanded] = useState(false);

  if (!cadContext.connected) {
    return (
      <div className="text-xs text-surface-500 italic">
        FreeCAD not connected -- using vision-only analysis
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-surface-400 hover:text-surface-200 font-mono uppercase tracking-wide mb-2"
      >
        {expanded ? '[-]' : '[+]'} {cadContext.document_name ?? 'CAD Document'} -- {cadContext.objects.length} objects, {cadContext.sketches.length} sketches
      </button>
      {expanded && (
        <div className="space-y-2 mt-2">
          {cadContext.objects.map((obj, i) => (
            <div key={i} className="bg-surface-800 border border-surface-600 p-2 text-xs font-mono">
              <span className="text-surface-200">{(obj as Record<string, unknown>).label as string ?? (obj as Record<string, unknown>).name as string}</span>
              <span className="text-surface-500 ml-2">{(obj as Record<string, unknown>).type as string}</span>
              {(obj as Record<string, unknown>).dimensions && (
                <div className="text-surface-400 mt-1">
                  {Object.entries((obj as Record<string, unknown>).dimensions as Record<string, number>)
                    .map(([k, v]) => `${k}: ${v}mm`)
                    .join(' | ')}
                </div>
              )}
            </div>
          ))}
          {cadContext.materials.length > 0 && (
            <div className="text-xs text-surface-400">
              Materials: {cadContext.materials.map(m => (m as Record<string, unknown>).material as string).join(', ')}
            </div>
          )}
          {cadContext.bounding_box && (
            <div className="text-xs text-surface-500 font-mono">
              Bounding box: {cadContext.bounding_box.x_max - cadContext.bounding_box.x_min} x {cadContext.bounding_box.y_max - cadContext.bounding_box.y_min} x {cadContext.bounding_box.z_max - cadContext.bounding_box.z_min} mm
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function AnalysisStream({ state }: Props) {
  if (state.status === 'idle') {
    return (
      <div className="flex items-center justify-center h-full text-surface-500 text-sm">
        Enter a feature description to begin analysis
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="p-6">
        <div className="bg-red-950/50 border border-red-800 p-4 text-red-300 text-sm">
          {state.error}
        </div>
      </div>
    );
  }

  const isActive = state.status === 'streaming' || state.status === 'connecting';

  return (
    <div className="p-6 overflow-y-auto h-full">
      {/* Features */}
      <Section
        title="Extracted Features"
        show={state.features !== null}
        pending={isActive && state.features === null}
      >
        {state.features && (
          <div className="space-y-2">
            {state.features.map((f, i) => (
              <div key={i} className="bg-surface-700 border border-surface-600 p-3 text-sm">
                <span className="text-surface-200 font-semibold">{f.feature_type}</span>
                {f.geometry.count != null && <span className="text-surface-400 ml-2">x{f.geometry.count}</span>}
                <div className="text-surface-400 mt-1 font-mono text-xs">
                  {Object.entries(f.geometry)
                    .filter(([k, v]) => k !== 'count' && v != null)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(' | ')}
                </div>
                <div className="text-surface-500 mt-1 text-xs">
                  {f.material} / {f.manufacturing_process}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* CAD Context */}
      {state.cadContext && (
        <Section
          title="CAD Context"
          show={state.cadContext !== null}
          pending={false}
        >
          <CADContextPanel cadContext={state.cadContext} />
        </Section>
      )}

      {/* Datum Scheme */}
      <Section
        title="Datum Scheme"
        show={state.datumScheme !== null}
        pending={isActive && state.datumScheme === null && state.features !== null}
      >
        {state.datumScheme && (
          <div className="flex gap-3">
            {[state.datumScheme.primary, state.datumScheme.secondary, state.datumScheme.tertiary]
              .filter(Boolean)
              .map((d) => (
                <div key={d!.datum} className="bg-surface-700 border border-surface-600 p-3 flex-1">
                  <div className="text-xl font-bold text-accent-400 font-mono">{d!.datum}</div>
                  <div className="text-sm text-surface-300 mt-1">{d!.surface}</div>
                  <div className="text-xs text-surface-500 mt-1">{d!.reasoning}</div>
                </div>
              ))}
          </div>
        )}
      </Section>

      {/* GDT Callouts */}
      <Section
        title="GD&T Callouts"
        show={state.callouts !== null}
        pending={isActive && state.callouts === null && state.datumScheme !== null}
      >
        {state.callouts?.map((callout, i) => (
          <GDTCallout key={i} callout={callout} />
        ))}
      </Section>

      {/* Reasoning */}
      <Section
        title="Reasoning"
        show={state.reasoning !== null}
        pending={isActive && state.reasoning === null && state.callouts !== null}
      >
        {state.reasoning && (
          <div className="space-y-3 text-sm">
            <p className="text-surface-300">{state.reasoning.summary}</p>
            <div className="bg-surface-700 border border-surface-600 p-3">
              <h4 className="text-xs font-semibold text-surface-400 font-mono uppercase mb-1">Manufacturing Notes</h4>
              <p className="text-surface-300">{state.reasoning.manufacturing_notes}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {state.reasoning.standards_references.map((ref) => (
                <span key={ref} className="px-2 py-1 bg-surface-700 border border-surface-600 text-xs text-surface-400 font-mono">
                  {ref}
                </span>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* Warnings */}
      <Section
        title="Warnings"
        show={state.warnings !== null && state.warnings.length > 0}
        pending={isActive && state.warnings === null && state.reasoning !== null}
      >
        {state.warnings?.map((warning, i) => (
          <div key={i} className="bg-accent-900/30 border border-accent-500/30 p-3 mb-2 text-sm text-yellow-200">
            {warning}
          </div>
        ))}
      </Section>
    </div>
  );
}
