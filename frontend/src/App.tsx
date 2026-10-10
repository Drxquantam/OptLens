import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Play, TerminalSquare } from 'lucide-react';
import { api } from './api';
import { CodeEditor, type FocusRequest } from './components/CodeEditor';
import { ErrorBoundary } from './components/ErrorBoundary';
import { PresetBanner } from './components/PresetBanner';
import { ResultsPanel, type TabId } from './components/ResultsPanel';
import { useToast } from './components/Toasts';
import { TopBar } from './components/TopBar';
import { useAnalysis } from './hooks/useAnalysis';
import type { Health, HistoryItem, Preset } from './types';

const STORAGE_KEY = 'optlens.draft';
const STARTER = `#include <stdio.h>

int main(void) {
    int total = 0;
    for (int i = 1; i <= 100; i++)
        total += i * i;
    printf("sum of squares = %d\\n", total);
    return 0;
}
`;

function loadDraft(): { source: string; stdin: string; presetId: string | null } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* storage unavailable */
  }
  return { source: STARTER, stdin: '', presetId: null };
}

export default function App() {
  const toast = useToast();
  const onError = useCallback((m: string) => toast('error', m), [toast]);
  const { state, run, load, busy } = useAnalysis(onError);

  const initial = useMemo(loadDraft, []);
  const [source, setSource] = useState(initial.source);
  const [stdin, setStdin] = useState(initial.stdin);
  const [presetId, setPresetId] = useState<string | null>(initial.presetId);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [tab, setTab] = useState<TabId>('verdict');
  const [focus, setFocus] = useState<FocusRequest | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  );

  useEffect(() => {
    api.presets().then(setPresets).catch(() => onError('Could not load examples from the API'));
    const check = () => api.health().then(setHealth).catch(() => setHealth(null));
    check();
    const t = setInterval(check, 15000);
    const jobId = new URLSearchParams(window.location.search).get('job');
    if (jobId) {
      void load(jobId).then((job) => {
        if (job?.source) {
          setSource(job.source);
          setStdin(job.stdin ?? '');
          setPresetId(job.preset_id);
        }
      });
    }
    return () => clearInterval(t);
  }, [load, onError]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ source, stdin, presetId }));
    } catch {
      /* storage unavailable */
    }
  }, [source, stdin, presetId]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try {
      localStorage.setItem('optlens.theme', theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);

  useEffect(() => {
    if (state.phase === 'done') {
      const url = new URL(window.location.href);
      url.searchParams.set('job', state.job.id);
      window.history.replaceState(null, '', url);
    }
  }, [state]);

  const doRun = useCallback(() => {
    if (busy || !source.trim()) return;
    setTab('verdict');
    void run(source, stdin, presetId);
  }, [busy, source, stdin, presetId, run]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        doRun();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [doRun]);

  const selectPreset = (id: string) => {
    const p = presets.find((x) => x.id === id);
    if (!p) return;
    setPresetId(p.id);
    setSource(p.source);
    setStdin(p.stdin);
  };

  const activePreset = presets.find((p) => p.id === presetId) ?? null;
  const result = state.phase === 'done' ? state.job.result : null;
  const stale = state.phase === 'done' && state.job.source != null && state.job.source !== source;
  const findings = useMemo(() => result?.verdict.evidence ?? [], [result]);
  const remarks = useMemo(() => result?.remarks ?? [], [result]);
  const jump = useCallback((line: number) => setFocus({ line, nonce: Date.now() }), []);

  return (
    <div className="flex h-full flex-col">
      <TopBar
        presets={presets}
        presetId={presetId}
        onPreset={selectPreset}
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        health={health}
        history={history}
        onOpenHistory={() => api.history().then(setHistory).catch(() => setHistory([]))}
        onLoadJob={(id) =>
          void load(id).then((job) => {
            if (job?.source) {
              setSource(job.source);
              setStdin(job.stdin ?? '');
              setPresetId(job.preset_id);
            }
          })
        }
      />

      <main className="scroll-thin flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
        {/* Editor column */}
        <section className="flex min-h-[460px] shrink-0 flex-col lg:shrink border-b hairline lg:w-[46%] lg:min-w-[380px] lg:border-b-0 lg:border-r">
          <div className="flex h-11 shrink-0 items-center gap-2 border-b px-3 hairline">
            <span className="font-mono text-xs text-muted">prog.c</span>
            <span className="text-[11px] text-faint">{source.split('\n').length} lines</span>
            <button
              onClick={doRun}
              disabled={busy || !source.trim()}
              className="ml-auto inline-flex items-center gap-2 rounded-lg bg-accent px-3.5 py-1.5 text-[13px] font-semibold text-white shadow-glow transition-all hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5 fill-current" />}
              {busy ? 'Running' : 'Run'}
              <kbd className="hidden rounded bg-white/15 px-1 font-mono text-[10px] font-medium sm:inline">Ctrl ⏎</kbd>
            </button>
          </div>
          {activePreset && (
            <PresetBanner preset={activePreset} modified={activePreset.source !== source} />
          )}
          <div className="min-h-0 flex-1">
            <CodeEditor
              value={source}
              onChange={(v) => {
                setSource(v);
              }}
              onRun={doRun}
              theme={theme}
              remarks={remarks}
              findings={findings}
              focus={focus}
            />
          </div>
          <div className="shrink-0 border-t hairline">
            <label className="flex items-center gap-2 px-3 pt-2 text-[11px] font-medium uppercase tracking-wider text-faint">
              <TerminalSquare className="h-3.5 w-3.5" /> stdin
            </label>
            <textarea
              value={stdin}
              onChange={(e) => setStdin(e.target.value)}
              placeholder="Optional input for the program"
              rows={2}
              spellCheck={false}
              className="scroll-thin block w-full resize-none bg-transparent px-3 pb-2 pt-1 font-mono text-[12.5px] text-fg outline-none placeholder:text-faint"
            />
          </div>
        </section>

        {/* Results column */}
        <ErrorBoundary resetKey={state}>
          <ResultsPanel
            stale={stale}
            state={state}
            tab={tab}
            onTab={setTab}
            onJump={jump}
            theme={theme}
            presets={presets}
            onPreset={selectPreset}
          />
        </ErrorBoundary>
      </main>
    </div>
  );
}
