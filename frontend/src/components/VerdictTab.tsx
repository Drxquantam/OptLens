import { ArrowUpRight, CheckCircle2, ShieldAlert, ShieldCheck, ShieldOff } from 'lucide-react';
import type { AnalysisResult, BuildOutcome, Finding, SanitizerOutcome } from '../types';
import { buildLabel, formatMs, statusLabel } from '../lib/format';
import { TONE, VERDICTS } from '../lib/verdict';
import { GroupChip } from './GroupChip';

interface Props {
  result: AnalysisResult;
  onJump: (line: number) => void;
}

const SANITIZER_TONE: Record<Finding['sanitizer'], string> = {
  UBSan: 'text-warn border-warn/30 bg-warn/10',
  ASan: 'text-bad border-bad/30 bg-bad/10',
  MSan: 'text-accent border-accent/30 bg-accent/10',
  'compiler-warning': 'text-neutral border-neutral/30 bg-neutral/10',
};

export function FindingRow({ f, onJump }: { f: Finding; onJump: (line: number) => void }) {
  return (
    <li className="flex items-start gap-2.5 rounded-lg border bg-panel/60 px-3 py-2 hairline">
      <span className={`chip mt-px shrink-0 ${SANITIZER_TONE[f.sanitizer]}`}>
        {f.sanitizer === 'compiler-warning' ? 'warning' : f.sanitizer}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[12.5px] leading-relaxed text-fg">{f.message}</p>
        <p className="text-[11px] text-faint">{f.kind}</p>
      </div>
      {f.line && (
        <button
          onClick={() => onJump(f.line!)}
          className="chip shrink-0 text-muted transition-colors hover:border-accent/40 hover:text-accent"
        >
          line {f.line}
          <ArrowUpRight className="h-3 w-3" />
        </button>
      )}
    </li>
  );
}

function VerdictCard({ result, onJump }: Props) {
  const v = result.verdict;
  const meta = VERDICTS[v.verdict];
  const tone = TONE[meta.tone];
  const Icon = meta.icon;
  return (
    <section className={`relative overflow-hidden rounded-2xl border ${tone.border} bg-panel shadow-soft`}>
      <div className={`pointer-events-none absolute inset-0 ${tone.bg} opacity-60`} />
      <div className="relative p-5">
        <div className="flex items-start gap-4">
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tone.bg} ring-1 ${tone.ring}`}>
            <Icon className={`h-6 w-6 ${tone.text}`} />
          </div>
          <div className="min-w-0">
            <div className={`text-[11px] font-semibold uppercase tracking-[0.12em] ${tone.text}`}>
              {v.verdict.replace(/_/g, ' ')}
            </div>
            <h2 className="mt-0.5 text-lg font-semibold leading-snug tracking-tight text-fg">{v.title}</h2>
          </div>
        </div>
        <p className="mt-3 text-[13.5px] leading-relaxed text-muted">{v.explanation}</p>

        {v.evidence.length > 0 && (
          <ul className="mt-4 space-y-1.5">
            {v.evidence.slice(0, 5).map((f, i) => (
              <FindingRow key={i} f={f} onJump={onJump} />
            ))}
          </ul>
        )}

        {v.details.length > 0 && (
          <ul className="mt-4 space-y-1 border-t pt-3 hairline">
            {v.details.map((d, i) => (
              <li key={i} className="flex gap-2 font-mono text-[12px] leading-relaxed text-muted">
                <span className="text-faint">›</span>
                <span className="min-w-0 break-words">{d}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function outputPreview(b: BuildOutcome): string {
  if (!b.compile_ok) return 'did not compile';
  if (b.status === 'timeout') return 'timed out';
  const first = b.stdout.split('\n').find((l) => l.trim()) ?? '';
  return first || '(no output)';
}

function MatrixTable({ builds }: { builds: BuildOutcome[] }) {
  const multi = new Set(builds.map((b) => b.group)).size > 1;
  return (
    <section className="card overflow-hidden">
      <header className="flex items-center justify-between border-b px-4 py-2.5 hairline">
        <h3 className="text-sm font-semibold">Compile matrix</h3>
        <span className="text-[11px] text-faint">same letter = identical stdout, exit code and signal</span>
      </header>
      <div className="scroll-thin overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-[12.5px]">
          <thead className="text-[11px] uppercase tracking-wider text-faint">
            <tr className="border-b hairline">
              <th className="px-4 py-2 font-medium">Build</th>
              <th className="px-2 py-2 font-medium">Group</th>
              <th className="px-2 py-2 font-medium">Status</th>
              <th className="px-2 py-2 font-medium">Output</th>
              <th className="px-2 py-2 font-medium">Hash</th>
              <th className="px-4 py-2 text-right font-medium">Runtime</th>
            </tr>
          </thead>
          <tbody>
            {builds.map((b) => {
              const differs = multi && b.group !== 0;
              return (
                <tr
                  key={b.id}
                  className={`border-b transition-colors last:border-0 hairline ${differs ? 'bg-warn/5' : 'hover:bg-raised/60'}`}
                >
                  <td className="whitespace-nowrap px-4 py-2 font-medium">
                    <span className={differs ? 'text-warn' : ''}>{buildLabel(b)}</span>
                  </td>
                  <td className="px-2 py-2">
                    <GroupChip group={b.group} />
                  </td>
                  <td className="whitespace-nowrap px-2 py-2">
                    <span
                      className={`chip ${b.status === 'ok' && b.exit_code === 0 ? 'text-ok' : 'text-warn'}`}
                      title={b.deterministic === false ? 'gave different results when re-run' : undefined}
                    >
                      {statusLabel(b)}
                      {b.deterministic === false && ' · flaky'}
                    </span>
                  </td>
                  <td className="max-w-[220px] truncate px-2 py-2 font-mono text-muted" title={b.stdout}>
                    {outputPreview(b)}
                  </td>
                  <td className="px-2 py-2 font-mono text-[11.5px] text-faint">{b.output_hash?.slice(0, 8) ?? '–'}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-right font-mono text-muted">{formatMs(b.runtime_ms)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SanitizerCard({ s }: { s: SanitizerOutcome }) {
  const clean = s.compiled && !s.timed_out && s.findings.length === 0;
  const Icon = !s.compiled ? ShieldOff : clean ? ShieldCheck : ShieldAlert;
  const color = !s.compiled ? 'text-neutral' : clean ? 'text-ok' : 'text-warn';
  const status = !s.compiled
    ? 'did not compile'
    : s.timed_out
      ? 'timed out'
      : clean
        ? 'clean'
        : `${s.findings.length} finding${s.findings.length > 1 ? 's' : ''}`;
  return (
    <div className="card p-3.5">
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${color}`} />
        <span className="text-sm font-medium">{s.name === 'msan' ? 'MemorySanitizer' : 'Address + UB Sanitizer'}</span>
        <span className={`ml-auto text-xs ${color}`}>{status}</span>
      </div>
      <p className="mt-1 font-mono text-[11px] text-faint">
        clang {s.name === 'msan' ? '-O0 -fsanitize=memory' : '-O1 -fsanitize=address,undefined'}
      </p>
      {(s.report || s.compile_stderr) && (
        <details className="group mt-2">
          <summary className="cursor-pointer select-none text-xs text-muted hover:text-fg">Raw report</summary>
          <pre className="scroll-thin mt-2 max-h-56 overflow-auto rounded-lg bg-raised p-2.5 font-mono text-[11px] leading-relaxed text-muted">
            {s.report || s.compile_stderr}
          </pre>
        </details>
      )}
    </div>
  );
}

export function VerdictTab({ result, onJump }: Props) {
  const ubWarnings = result.warnings.filter((w) => !result.verdict.evidence.includes(w));
  return (
    <div className="space-y-4">
      <VerdictCard result={result} onJump={onJump} />
      <MatrixTable builds={result.builds} />
      <div className="grid gap-3 sm:grid-cols-2">
        {result.sanitizers.map((s) => (
          <SanitizerCard key={s.name} s={s} />
        ))}
      </div>
      {ubWarnings.length > 0 && result.verdict.verdict !== 'MISMATCH_UB' && (
        <section className="card p-4">
          <h3 className="mb-2 text-sm font-semibold">Compiler warnings worth a look</h3>
          <ul className="space-y-1.5">
            {ubWarnings.map((f, i) => (
              <FindingRow key={i} f={f} onJump={onJump} />
            ))}
          </ul>
        </section>
      )}
      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-[11px] text-faint">
        <span className="inline-flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3" /> {result.toolchain.gcc}
        </span>
        <span className="inline-flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3" /> {result.toolchain.clang}
        </span>
        {result.limits.run_timeout_s && <span>run limit {result.limits.run_timeout_s}s per build</span>}
      </footer>
    </div>
  );
}
