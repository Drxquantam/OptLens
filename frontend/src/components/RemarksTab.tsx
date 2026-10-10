import { useMemo, useState } from 'react';
import { CheckCircle2, CircleSlash, Info, Sparkles } from 'lucide-react';
import type { Remark } from '../types';

interface Props {
  remarks: Remark[];
  truncated: boolean;
  onJump: (line: number) => void;
}

const PASS_NAMES: Record<string, string> = {
  inline: 'Inliner',
  'loop-vectorize': 'Loop vectorizer',
  'slp-vectorizer': 'SLP vectorizer',
  'loop-unroll': 'Loop unroller',
  'loop-delete': 'Loop deletion',
  'loop-idiom': 'Loop idiom recognition',
  licm: 'Loop-invariant code motion',
  gvn: 'Global value numbering',
  dse: 'Dead store elimination',
  sroa: 'Scalar replacement of aggregates',
  sccp: 'Constant propagation',
  ipsccp: 'Interprocedural constant propagation',
  tailcallelim: 'Tail-call elimination',
  'transform-warning': 'Transformation warnings',
  regalloc: 'Register allocator',
  prologepilog: 'Stack frame',
  'asm-printer': 'Code size',
  memcpyopt: 'memcpy optimizer',
  'loop-distribute': 'Loop distribution',
  'loop-interchange': 'Loop interchange',
};

type Kind = Remark['kind'];
const KINDS: { id: Kind; label: string; icon: typeof CheckCircle2; color: string }[] = [
  { id: 'passed', label: 'Applied', icon: CheckCircle2, color: 'text-ok' },
  { id: 'missed', label: 'Missed', icon: CircleSlash, color: 'text-warn' },
  { id: 'analysis', label: 'Analysis', icon: Info, color: 'text-neutral' },
];

export function RemarksTab({ remarks, truncated, onJump }: Props) {
  const [enabled, setEnabled] = useState<Record<Kind, boolean>>({ passed: true, missed: true, analysis: false });

  const counts = useMemo(() => {
    const c: Record<Kind, number> = { passed: 0, missed: 0, analysis: 0 };
    for (const r of remarks) c[r.kind]++;
    return c;
  }, [remarks]);

  const groups = useMemo(() => {
    const map = new Map<string, Remark[]>();
    for (const r of remarks) {
      if (!enabled[r.kind]) continue;
      map.set(r.pass_name, [...(map.get(r.pass_name) ?? []), r]);
    }
    const score = (rs: Remark[]) => (rs.some((r) => r.kind === 'passed') ? 1000 : 0) + rs.length;
    return [...map.entries()]
      .map(([pass, rs]) => [pass, [...rs].sort((a, b) => (a.line ?? 1e9) - (b.line ?? 1e9))] as const)
      .sort((a, b) => score(b[1]) - score(a[1]));
  }, [remarks, enabled]);

  if (remarks.length === 0) {
    return (
      <div className="flex flex-col items-center py-16 text-center">
        <Sparkles className="mb-3 h-8 w-8 text-faint" />
        <p className="text-sm text-muted">Clang reported no optimization remarks for this program.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {KINDS.map((k) => {
          const Icon = k.icon;
          const on = enabled[k.id];
          return (
            <button
              key={k.id}
              onClick={() => setEnabled({ ...enabled, [k.id]: !on })}
              aria-pressed={on}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all hairline ${
                on ? 'bg-raised text-fg' : 'text-faint opacity-70 hover:opacity-100'
              }`}
            >
              <Icon className={`h-3.5 w-3.5 ${on ? k.color : ''}`} />
              {k.label}
              <span className="font-mono text-[11px] text-faint">{counts[k.id]}</span>
            </button>
          );
        })}
        <span className="ml-auto text-[11px] text-faint">
          clang -O3 -Rpass=.* -Rpass-missed=.* -Rpass-analysis=.*
        </span>
      </div>

      {groups.length === 0 && <p className="py-8 text-center text-sm text-faint">No remarks match the filters.</p>}

      {groups.map(([pass, rs]) => (
        <section key={pass} className="card overflow-hidden">
          <header className="flex items-center gap-2 border-b px-4 py-2 hairline">
            <h3 className="text-sm font-semibold">{PASS_NAMES[pass] ?? pass}</h3>
            <code className="font-mono text-[11px] text-faint">{pass}</code>
            <span className="ml-auto font-mono text-[11px] text-faint">{rs.length}</span>
          </header>
          <ul>
            {rs.map((r, i) => {
              const k = KINDS.find((x) => x.id === r.kind)!;
              const Icon = k.icon;
              return (
                <li key={i} className="border-b last:border-0 hairline">
                  <button
                    disabled={!r.line}
                    onClick={() => r.line && onJump(r.line)}
                    className="group flex w-full items-start gap-3 px-4 py-2 text-left transition-colors enabled:hover:bg-raised/70 disabled:cursor-default"
                  >
                    <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${k.color}`} />
                    <span className="min-w-0 flex-1 font-mono text-[12px] leading-relaxed text-muted group-hover:text-fg">
                      {r.message}
                    </span>
                    {r.line && (
                      <span className="chip shrink-0 font-mono text-faint group-hover:border-accent/40 group-hover:text-accent">
                        L{r.line}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {truncated && <p className="text-center text-[11px] text-faint">Remark list truncated at the server cap.</p>}
    </div>
  );
}
