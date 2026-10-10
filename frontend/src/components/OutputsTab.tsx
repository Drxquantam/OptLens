import { useState } from 'react';
import type { AnalysisResult, BuildOutcome } from '../types';
import { buildLabel, formatMs, statusLabel } from '../lib/format';
import { GroupChip } from './GroupChip';

function DiffedOutput({ text, reference }: { text: string; reference: string | null }) {
  const lines = text.length ? text.replace(/\n$/, '').split('\n') : [];
  const ref = reference?.replace(/\n$/, '').split('\n') ?? null;
  if (lines.length === 0) return <p className="px-3 py-2.5 font-mono text-[12px] italic text-faint">(no output)</p>;
  return (
    <pre className="scroll-thin max-h-72 overflow-auto py-1.5 font-mono text-[12px] leading-[1.6]">
      {lines.map((line, i) => {
        const differs = ref !== null && ref[i] !== line;
        return (
          <div key={i} className={`flex px-3 ${differs ? 'bg-warn/10 text-fg' : 'text-muted'}`}>
            <span className="mr-3 w-6 shrink-0 select-none text-right text-faint/70">{i + 1}</span>
            <span className="whitespace-pre-wrap break-all">{line || ' '}</span>
          </div>
        );
      })}
    </pre>
  );
}

function OutputCard({ b, reference }: { b: BuildOutcome; reference: BuildOutcome | null }) {
  const isRef = reference?.id === b.id;
  const differs = reference !== null && b.group !== reference.group;
  return (
    <article className={`card overflow-hidden ${differs ? 'border-warn/40' : ''}`}>
      <header className="flex flex-wrap items-center gap-2 border-b px-3 py-2 hairline">
        <GroupChip group={b.group} />
        <span className="text-sm font-medium">{buildLabel(b)}</span>
        {isRef && <span className="chip text-faint">reference</span>}
        {differs && <span className="chip border-warn/30 text-warn">differs</span>}
        <span className="ml-auto flex items-center gap-3 font-mono text-[11px] text-faint">
          <span>{statusLabel(b)}</span>
          <span>{formatMs(b.runtime_ms)}</span>
        </span>
      </header>
      {!b.compile_ok ? (
        <pre className="scroll-thin max-h-60 overflow-auto p-3 font-mono text-[11.5px] leading-relaxed text-bad">
          {b.compile_stderr}
        </pre>
      ) : (
        <>
          <DiffedOutput text={b.stdout} reference={isRef || !reference ? null : reference.stdout} />
          {b.stdout_truncated && (
            <p className="border-t px-3 py-1.5 text-[11px] text-faint hairline">output truncated at the sandbox cap</p>
          )}
          {b.stderr.trim() && (
            <details className="border-t hairline">
              <summary className="cursor-pointer px-3 py-1.5 text-[11px] text-muted hover:text-fg">stderr</summary>
              <pre className="scroll-thin max-h-40 overflow-auto px-3 pb-2 font-mono text-[11.5px] text-muted">
                {b.stderr}
              </pre>
            </details>
          )}
        </>
      )}
    </article>
  );
}

export function OutputsTab({ result }: { result: AnalysisResult }) {
  const [onlyDiff, setOnlyDiff] = useState(false);
  const reference = result.builds.find((b) => b.group === 0) ?? null;
  const anyDiff = new Set(result.builds.map((b) => b.group)).size > 1;
  const shown = onlyDiff ? result.builds.filter((b) => b.group !== 0 || b.id === reference?.id) : result.builds;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[12.5px] text-muted">
          {anyDiff
            ? 'Lines that differ from the reference build (largest group) are highlighted.'
            : 'Every build printed exactly the same thing.'}
        </p>
        {anyDiff && (
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
            <input
              type="checkbox"
              checked={onlyDiff}
              onChange={(e) => setOnlyDiff(e.target.checked)}
              className="accent-[rgb(var(--accent))]"
            />
            only differing
          </label>
        )}
      </div>
      <div className="grid gap-3 2xl:grid-cols-2">
        {shown.map((b) => (
          <OutputCard key={b.id} b={b} reference={anyDiff ? reference : null} />
        ))}
      </div>
    </div>
  );
}
