import { useEffect, useMemo, useRef, useState } from 'react';
import { DiffEditor } from '@monaco-editor/react';
import { ArrowLeftRight, TrendingDown, TrendingUp } from 'lucide-react';
import type { AnalysisResult, BuildOutcome } from '../types';
import { buildLabel, compilerLabel } from '../lib/format';
import type { monaco } from '../monaco';

interface Props {
  result: AnalysisResult;
  theme: 'dark' | 'light';
}

const DIFF_OPTIONS: monaco.editor.IDiffEditorConstructionOptions = {
  readOnly: true,
  originalEditable: false,
  renderSideBySide: true,
  useInlineViewWhenSpaceIsLimited: true,
  renderSideBySideInlineBreakpoint: 520,
  renderOverviewRuler: false,
  minimap: { enabled: false },
  fontFamily: '"JetBrains Mono", ui-monospace, monospace',
  fontSize: 12,
  lineHeight: 19,
  scrollBeyondLastLine: false,
  automaticLayout: true,
  ignoreTrimWhitespace: false,
  padding: { top: 8 },
  scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
};

function BuildSelect({
  label,
  value,
  builds,
  onChange,
}: {
  label: string;
  value: string;
  builds: BuildOutcome[];
  onChange: (id: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-faint">
      {label}
      <select className="select py-1 text-[13px]" value={value} onChange={(e) => onChange(e.target.value)}>
        {builds.map((b) => (
          <option key={b.id} value={b.id} disabled={b.asm == null}>
            {buildLabel(b)}
          </option>
        ))}
      </select>
    </label>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wider text-faint">{label}</div>
      <div className="font-mono text-lg font-semibold tabular-nums text-fg">{value}</div>
      {hint && <div className="truncate text-[11px] text-faint">{hint}</div>}
    </div>
  );
}

export function AssemblyTab({ result, theme }: Props) {
  const builds = result.builds;
  const compilers = [...new Set(builds.map((b) => b.compiler))];
  const [leftId, setLeftId] = useState(() => `${compilers[0]}-O0`);
  const [rightId, setRightId] = useState(() => `${compilers[0]}-O3`);
  const left = builds.find((b) => b.id === leftId);
  const right = builds.find((b) => b.id === rightId);
  const activeCompiler = left?.compiler === right?.compiler ? left?.compiler : null;

  // Detach the models before @monaco-editor/react disposes them on unmount.
  // Otherwise Monaco throws "TextModel got disposed before DiffEditorWidget model
  // got reset". This parent cleanup runs before the DiffEditor's own cleanup.
  const diffRef = useRef<monaco.editor.IStandaloneDiffEditor | null>(null);
  useEffect(
    () => () => {
      diffRef.current?.setModel(null);
      diffRef.current = null;
    },
    [],
  );

  const delta = useMemo(() => {
    const a = left?.asm_instructions;
    const b = right?.asm_instructions;
    if (a == null || b == null || a === 0) return null;
    return Math.round(((b - a) / a) * 100);
  }, [left, right]);

  if (!left || !right) return null;

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg border bg-raised p-0.5 hairline" role="radiogroup" aria-label="Compiler">
          {compilers.map((cc) => (
            <button
              key={cc}
              role="radio"
              aria-checked={activeCompiler === cc}
              onClick={() => {
                setLeftId(`${cc}-O0`);
                setRightId(`${cc}-O3`);
              }}
              className={`rounded-md px-3 py-1 text-[13px] font-medium transition-all ${
                activeCompiler === cc ? 'bg-panel text-fg shadow-soft' : 'text-muted hover:text-fg'
              }`}
            >
              {compilerLabel(cc)}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <BuildSelect label="Left" value={leftId} builds={builds} onChange={setLeftId} />
          <button
            className="btn-ghost px-1.5"
            onClick={() => {
              setLeftId(rightId);
              setRightId(leftId);
            }}
            aria-label="Swap builds"
            title="Swap"
          >
            <ArrowLeftRight className="h-3.5 w-3.5" />
          </button>
          <BuildSelect label="Right" value={rightId} builds={builds} onChange={setRightId} />
        </div>
      </div>

      <div className="card grid grid-cols-2 gap-4 p-4 sm:grid-cols-4">
        <Stat label={buildLabel(left)} value={`${left.asm_instructions ?? '–'}`} hint="instructions" />
        <Stat label={buildLabel(right)} value={`${right.asm_instructions ?? '–'}`} hint="instructions" />
        <div className="col-span-2 flex items-center gap-3">
          {delta !== null && delta !== 0 ? (
            <>
              <div
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                  delta < 0 ? 'bg-ok/10 text-ok' : 'bg-warn/10 text-warn'
                }`}
              >
                {delta < 0 ? <TrendingDown className="h-5 w-5" /> : <TrendingUp className="h-5 w-5" />}
              </div>
              <p className="text-[13px] leading-snug text-muted">
                <span className="font-semibold text-fg">{buildLabel(right)}</span> has{' '}
                <span className={`font-semibold ${delta < 0 ? 'text-ok' : 'text-warn'}`}>
                  {Math.abs(delta)}% {delta < 0 ? 'fewer' : 'more'}
                </span>{' '}
                instructions than {buildLabel(left)}
                {delta > 0 && (
                  <span className="text-faint"> (unrolling, vectorization and inlining often trade size for speed)</span>
                )}
              </p>
            </>
          ) : (
            <p className="text-[13px] text-muted">Same instruction count in both builds.</p>
          )}
        </div>
      </div>

      <div className="card min-h-[440px] flex-1 overflow-hidden">
        <DiffEditor
          original={left.asm ?? '; no assembly (compile failed)'}
          modified={right.asm ?? '; no assembly (compile failed)'}
          language="x86asm"
          onMount={(editor) => {
            diffRef.current = editor;
          }}
          theme={theme === 'dark' ? 'optlens-dark' : 'optlens-light'}
          options={DIFF_OPTIONS}
          loading={<div className="h-full w-full animate-pulse bg-panel" />}
        />
      </div>
      <p className="px-1 text-[11px] text-faint">
        Intel syntax, compiled with <code className="font-mono">-S -masm=intel</code>. Directives and debug/unwind noise
        are stripped; labels, instructions and data are kept. Instruction counts cover the whole translation unit.
        {(left.asm_truncated || right.asm_truncated) && ' Output was truncated at the sandbox line cap.'}
      </p>
    </div>
  );
}
