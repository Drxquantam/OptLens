import { useEffect, useState, type ReactNode } from 'react';
import { AlertOctagon, FlaskConical, Keyboard, Loader2 } from 'lucide-react';
import type { RunState } from '../hooks/useAnalysis';
import type { Preset } from '../types';
import { TONE, VERDICTS } from '../lib/verdict';
import { AssemblyTab } from './AssemblyTab';
import { OutputsTab } from './OutputsTab';
import { VerdictChip } from './PresetBanner';
import { RemarksTab } from './RemarksTab';
import { VerdictTab } from './VerdictTab';

export type TabId = 'verdict' | 'outputs' | 'assembly' | 'remarks';

interface Props {
  state: RunState;
  tab: TabId;
  onTab: (t: TabId) => void;
  onJump: (line: number) => void;
  theme: 'dark' | 'light';
  stale: boolean;
  presets: Preset[];
  onPreset: (id: string) => void;
}

const TABS: { id: TabId; label: string; short: string }[] = [
  { id: 'verdict', label: 'Verdict', short: 'Verdict' },
  { id: 'outputs', label: 'Outputs', short: 'Outputs' },
  { id: 'assembly', label: 'Assembly Diff', short: 'Asm' },
  { id: 'remarks', label: 'Optimizer Remarks', short: 'Remarks' },
];

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, []);
  return <span className="font-mono tabular-nums">{((now - since) / 1000).toFixed(1)}s</span>;
}

function Bar({ className = '' }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-md bg-raised ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-line/5 to-transparent" />
    </div>
  );
}

function Loading({ state }: { state: Extract<RunState, { startedAt: number }> }) {
  const label =
    state.phase === 'submitting'
      ? 'Submitting…'
      : state.phase === 'queued'
        ? `Queued${state.position ? ` · position ${state.position}` : ''}`
        : 'Compiling 6 builds + 2 sanitizer builds, running in the sandbox…';
  return (
    <div className="space-y-4 animate-fade-in">
      <div className="card flex items-center gap-3 p-4">
        <Loader2 className="h-5 w-5 animate-spin text-accent" />
        <div className="min-w-0 flex-1 text-sm">
          <div className="font-medium text-fg">{label}</div>
          <div className="text-xs text-faint">
            GCC & Clang × -O0/-O2/-O3, ASan+UBSan, MSan, assembly and optimizer remarks
          </div>
        </div>
        <span className="text-xs text-muted">
          <Elapsed since={state.startedAt} />
        </span>
      </div>
      <div className="card space-y-3 p-5">
        <Bar className="h-4 w-40" />
        <Bar className="h-6 w-3/4" />
        <Bar className="h-3 w-full" />
        <Bar className="h-3 w-5/6" />
      </div>
      <div className="card space-y-2.5 p-4">
        {Array.from({ length: 6 }, (_, i) => (
          <Bar key={i} className="h-5 w-full" />
        ))}
      </div>
    </div>
  );
}

function Empty({ presets, onPreset }: { presets: Preset[]; onPreset: (id: string) => void }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center px-2 py-10 text-center animate-fade-in">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 ring-1 ring-accent/20">
        <FlaskConical className="h-7 w-7 text-accent" />
      </div>
      <h2 className="text-base font-semibold">Differential-test your C code</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
        OptLens compiles your program with GCC and Clang at three optimization levels, runs every build in an
        isolated sandbox, and tells you whether the optimizer changed its behaviour, and if so, whether it is your
        bug or the compiler&apos;s.
      </p>
      {presets.length > 0 && (
        <div className="mt-7 grid w-full gap-2 text-left sm:grid-cols-2">
          {presets.map((p) => (
            <button
              key={p.id}
              onClick={() => onPreset(p.id)}
              className="card group flex flex-col gap-1.5 p-3 transition-all hover:-translate-y-px hover:border-accent/40 hover:shadow-glow"
            >
              <span className="flex w-full items-center gap-2">
                <span className="truncate text-[13px] font-medium text-fg">{p.title}</span>
                <span className="ml-auto shrink-0">
                  <VerdictChip verdict={p.expected_verdict} />
                </span>
              </span>
              <span className="text-[11px] text-faint">{p.category}</span>
            </button>
          ))}
        </div>
      )}
      <p className="mt-6 inline-flex flex-wrap items-center justify-center gap-2 text-xs text-faint">
        <Keyboard className="h-3.5 w-3.5" />
        Load an example or write your own, then press
        <kbd className="rounded border bg-raised px-1.5 py-0.5 font-mono text-[11px] text-muted hairline">Ctrl</kbd>+
        <kbd className="rounded border bg-raised px-1.5 py-0.5 font-mono text-[11px] text-muted hairline">Enter</kbd>
      </p>
    </div>
  );
}

function Failed({ error }: { error: string }) {
  return (
    <div className="card flex items-start gap-3 border-bad/30 p-5 animate-fade-in">
      <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-bad" />
      <div>
        <h2 className="font-semibold">The analysis could not run</h2>
        <p className="mt-1 text-sm text-muted">{error}</p>
        <p className="mt-3 text-xs text-faint">
          This is a problem with the sandbox or the service, not with your program. Check that Docker is running and
          the <code className="font-mono">optlens-sandbox</code> image is built.
        </p>
      </div>
    </div>
  );
}

export function ResultsPanel({ state, tab, onTab, onJump, theme, stale, presets, onPreset }: Props) {
  const result = state.phase === 'done' ? state.job.result : null;
  let body: ReactNode;
  if (state.phase === 'idle') body = <Empty presets={presets} onPreset={onPreset} />;
  else if (state.phase === 'failed') body = <Failed error={state.error} />;
  else if (state.phase !== 'done') body = <Loading state={state} />;
  else if (!result) body = <Failed error="The job finished without a result." />;
  else
    body = (
      <div key={state.job.id} className={`animate-fade-in ${tab === 'assembly' ? 'h-full' : ''}`}>
        {tab === 'verdict' && <VerdictTab result={result} onJump={onJump} />}
        {tab === 'outputs' && <OutputsTab result={result} />}
        {tab === 'assembly' && <AssemblyTab result={result} theme={theme} />}
        {tab === 'remarks' && (
          <RemarksTab remarks={result.remarks} truncated={result.remarks_truncated} onJump={onJump} />
        )}
      </div>
    );

  const meta = result ? VERDICTS[result.verdict.verdict] : null;

  return (
    <section className="flex min-h-[640px] flex-1 flex-col lg:min-h-0">
      <nav className="scroll-thin flex h-11 shrink-0 items-center gap-1 overflow-x-auto border-b px-3 hairline" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            disabled={!result}
            onClick={() => onTab(t.id)}
            className={`relative shrink-0 whitespace-nowrap rounded-md px-2.5 py-1.5 text-[13px] sm:px-3 font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              tab === t.id ? 'text-fg' : 'text-muted hover:text-fg'
            }`}
          >
            <span className="hidden sm:inline">{t.label}</span>
            <span className="sm:hidden">{t.short}</span>
            {t.id === 'remarks' && result && result.remarks.length > 0 && (
              <span className="ml-1.5 rounded bg-raised px-1 font-mono text-[10px] text-faint">
                {result.remarks.filter((r) => r.kind !== 'analysis').length}
              </span>
            )}
            {tab === t.id && result && (
              <span className="absolute inset-x-2 -bottom-[7px] h-0.5 rounded-full bg-accent" />
            )}
          </button>
        ))}
        {stale && (
          <span className="ml-auto hidden text-[11px] text-faint xl:inline" title="Run again to analyse the current code">
            code changed since this run
          </span>
        )}
        {meta && (
          <span className={`chip shrink-0 ${stale ? 'ml-2' : 'ml-auto'} ${TONE[meta.tone].text} ${TONE[meta.tone].border}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${TONE[meta.tone].dot}`} />
            {meta.label}
          </span>
        )}
      </nav>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto p-4">{body}</div>
    </section>
  );
}
