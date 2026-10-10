import { useEffect, useRef } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { monaco } from '../monaco';
import type { Finding, Remark } from '../types';

export interface FocusRequest {
  line: number;
  nonce: number;
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
  theme: 'dark' | 'light';
  remarks: Remark[];
  findings: Finding[];
  focus: FocusRequest | null;
}

const EDITOR_OPTIONS: monaco.editor.IStandaloneEditorConstructionOptions = {
  fontFamily: '"JetBrains Mono", ui-monospace, monospace',
  fontSize: 13,
  lineHeight: 20,
  fontLigatures: true,
  minimap: { enabled: false },
  glyphMargin: true,
  scrollBeyondLastLine: false,
  smoothScrolling: true,
  cursorSmoothCaretAnimation: 'on',
  padding: { top: 12, bottom: 12 },
  renderLineHighlight: 'all',
  automaticLayout: true,
  tabSize: 4,
  scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
  overviewRulerBorder: false,
  hideCursorInOverviewRuler: true,
};

function summarize(remarks: Remark[]): string {
  return remarks
    .slice(0, 6)
    .map((r) => `- **${r.pass_name}**${r.kind === 'missed' ? ' (missed)' : ''}: ${r.message}`)
    .join('\n');
}

export function CodeEditor({ value, onChange, onRun, theme, remarks, findings, focus }: Props) {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const markers = useRef<monaco.editor.IEditorDecorationsCollection | null>(null);
  const focusDeco = useRef<monaco.editor.IEditorDecorationsCollection | null>(null);
  const runRef = useRef(onRun);
  runRef.current = onRun;

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
    markers.current = editor.createDecorationsCollection();
    focusDeco.current = editor.createDecorationsCollection();
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current());
  };

  // Gutter markers: optimizer remarks (dots) and sanitizer findings (diamonds).
  useEffect(() => {
    if (!markers.current) return;
    const byLine = new Map<number, Remark[]>();
    for (const r of remarks) {
      if (r.line && r.kind !== 'analysis') byLine.set(r.line, [...(byLine.get(r.line) ?? []), r]);
    }
    const decorations: monaco.editor.IModelDeltaDecoration[] = [];
    for (const [line, rs] of byLine) {
      const onlyMissed = rs.every((r) => r.kind === 'missed');
      decorations.push({
        range: new monaco.Range(line, 1, line, 1),
        options: {
          glyphMarginClassName: onlyMissed ? 'remark-glyph remark-glyph-missed' : 'remark-glyph',
          glyphMarginHoverMessage: { value: `**Optimizer remarks**\n\n${summarize(rs)}` },
        },
      });
    }
    for (const f of findings) {
      if (!f.line) continue;
      decorations.push({
        range: new monaco.Range(f.line, 1, f.line, 1),
        options: {
          isWholeLine: true,
          className: 'finding-line',
          glyphMarginClassName: 'finding-glyph',
          glyphMarginHoverMessage: { value: `**${f.sanitizer}** · ${f.kind}\n\n${f.message}` },
        },
      });
    }
    markers.current.set(decorations);
  }, [remarks, findings, value]);

  // Jump to a line requested from the Remarks / Verdict tabs.
  useEffect(() => {
    const editor = editorRef.current;
    if (!editor || !focus) return;
    editor.revealLineInCenter(focus.line, monaco.editor.ScrollType.Smooth);
    editor.setPosition({ lineNumber: focus.line, column: 1 });
    editor.focus();
    focusDeco.current?.set([
      { range: new monaco.Range(focus.line, 1, focus.line, 1), options: { isWholeLine: true, className: 'focus-line' } },
    ]);
    const t = setTimeout(() => focusDeco.current?.clear(), 1800);
    return () => clearTimeout(t);
  }, [focus]);

  return (
    <Editor
      language="c"
      value={value}
      onChange={(v) => onChange(v ?? '')}
      theme={theme === 'dark' ? 'optlens-dark' : 'optlens-light'}
      options={EDITOR_OPTIONS}
      onMount={handleMount}
      loading={<div className="h-full w-full animate-pulse bg-panel" />}
    />
  );
}
