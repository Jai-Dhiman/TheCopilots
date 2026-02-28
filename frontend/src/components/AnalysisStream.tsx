import type { ReactNode } from 'react';
import type { AnalysisState } from '../types';
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
          className="h-4 bg-surface-700 rounded animate-pulse"
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
      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
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

export function AnalysisStream({ state }: Props) {
  if (state.status === 'idle') {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Enter a feature description to begin analysis
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="p-6">
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 text-red-300 text-sm">
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
              <div key={i} className="bg-surface-700 rounded-lg p-3 text-sm">
                <span className="text-slate-200 font-semibold">{f.feature_type}</span>
                {f.count && <span className="text-slate-400 ml-2">x{f.count}</span>}
                <div className="text-slate-400 mt-1 font-mono text-xs">
                  {Object.entries(f.geometry).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

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
                <div key={d!.datum} className="bg-surface-700 rounded-lg p-3 flex-1">
                  <div className="text-xl font-bold text-slate-200">{d!.datum}</div>
                  <div className="text-sm text-slate-300 mt-1">{d!.surface}</div>
                  <div className="text-xs text-slate-500 mt-1">{d!.reasoning}</div>
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
            <p className="text-slate-300">{state.reasoning.summary}</p>
            <div className="bg-surface-700 rounded-lg p-3">
              <h4 className="text-xs font-semibold text-slate-400 uppercase mb-1">Manufacturing Notes</h4>
              <p className="text-slate-300">{state.reasoning.manufacturing_notes}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {state.reasoning.standards_references.map((ref) => (
                <span key={ref} className="px-2 py-1 bg-surface-700 rounded text-xs text-slate-400 font-mono">
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
          <div key={i} className="bg-yellow-950/30 border border-yellow-800/50 rounded-lg p-3 mb-2 text-sm text-yellow-200">
            {warning}
          </div>
        ))}
      </Section>
    </div>
  );
}
