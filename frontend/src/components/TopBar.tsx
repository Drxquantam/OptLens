import { useEffect, useRef, useState } from 'react';
import { ChevronDown, History, Moon, Sun } from 'lucide-react';
import type { Health, HistoryItem, Preset } from '../types';
import { relativeTime } from '../lib/format';
import { TONE, VERDICTS } from '../lib/verdict';

interface Props {
  presets: Preset[];
  presetId: string | null;
  onPreset: (id: string) => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  health: Health | null;
  history: HistoryItem[];
  onOpenHistory: () => void;
  onLoadJob: (id: string) => void;
}

export function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
      <rect width="32" height="32" rx="8" className="fill-raised" />
      <circle cx="14" cy="14" r="7" fill="none" className="stroke-accent" strokeWidth="2.5" />
      <path d="M19 19l6 6" className="stroke-accent" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M11 14h6M14 11v6" className="stroke-fg" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function HealthDot({ health }: { health: Health | null }) {
  const ok = health?.status === 'ok';
  const label = !health
    ? 'API unreachable'
    : ok
      ? `Sandbox ready · ${health.running} running · ${health.queued} queued`
      : !health.docker
        ? 'Docker is not reachable from the API'
        : `Sandbox image ${health.image} not built`;
  return (
    <span className="hidden items-center gap-2 text-xs text-faint lg:flex" title={label}>
      <span className="relative flex h-2 w-2">
        {ok && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok/50" />}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${ok ? 'bg-ok' : 'bg-bad'}`} />
      </span>
      {ok ? 'sandbox ready' : 'sandbox offline'}
    </span>
  );
}

export function TopBar(p: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const categories = [...new Set(p.presets.map((x) => x.category))];

  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center gap-3 border-b bg-panel/80 px-4 backdrop-blur hairline">
      <div className="flex min-w-0 shrink items-center gap-2.5">
        <Logo />
        <div className="min-w-0">
          <div className="hidden text-[15px] font-semibold tracking-tight min-[400px]:block">OptLens</div>
          <div className="hidden truncate text-[11px] text-faint sm:block">
            See what the optimizer did, and whether it changed your program
          </div>
        </div>
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1">
        <HealthDot health={p.health} />

        <div className="relative" ref={ref}>
          <button
            className="btn-ghost"
            onClick={() => {
              if (!open) p.onOpenHistory();
              setOpen(!open);
            }}
            aria-expanded={open}
          >
            <History className="h-4 w-4" />
            <span className="hidden md:inline">History</span>
          </button>
          {open && (
            <div className="card scroll-thin absolute right-0 top-10 z-40 max-h-[min(70vh,480px)] w-80 animate-fade-in overflow-y-auto p-1">
              {p.history.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-faint">No runs yet</p>
              ) : (
                p.history.map((h) => {
                  const meta = VERDICTS[h.verdict];
                  return (
                    <button
                      key={h.id}
                      onClick={() => {
                        setOpen(false);
                        p.onLoadJob(h.id);
                      }}
                      className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-raised"
                    >
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE[meta.tone].dot}`} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-mono text-xs text-fg">{h.source_preview}</span>
                        <span className="text-[11px] text-faint">
                          {meta.label} · {relativeTime(h.created_at)}
                        </span>
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>

        <button className="btn-ghost" onClick={p.onToggleTheme} aria-label="Toggle colour theme">
          {p.theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>

        <label className="relative">
          <span className="sr-only">Load an example</span>
          <select
            className="select w-[150px] appearance-none truncate pr-8 font-medium sm:w-auto sm:max-w-[260px]"
            value={p.presetId ?? ''}
            onChange={(e) => p.onPreset(e.target.value)}
          >
            <option value="" disabled>
              Examples…
            </option>
            {categories.map((cat) => (
              <optgroup key={cat} label={cat}>
                {p.presets
                  .filter((x) => x.category === cat)
                  .map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.title}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-faint" />
        </label>
      </div>
    </header>
  );
}
