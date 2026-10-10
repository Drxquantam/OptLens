import { useState } from 'react';
import { BookOpen, ChevronDown, Pencil } from 'lucide-react';
import type { Preset } from '../types';
import { TONE, VERDICTS } from '../lib/verdict';

/** Renders `code` spans in preset summaries. */
export function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split(/(`[^`]+`)/g).map((part, i) =>
        part.startsWith('`') ? (
          <code key={i} className="rounded bg-raised px-1 py-px font-mono text-[0.92em] text-fg">
            {part.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export function VerdictChip({ verdict }: { verdict: Preset['expected_verdict'] }) {
  const meta = VERDICTS[verdict];
  const tone = TONE[meta.tone];
  return (
    <span className={`chip ${tone.text} ${tone.border}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
      {meta.label}
    </span>
  );
}

export function PresetBanner({ preset, modified }: { preset: Preset; modified: boolean }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="shrink-0 border-b bg-raised/40 hairline">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
        aria-expanded={open}
      >
        <BookOpen className="h-3.5 w-3.5 shrink-0 text-accent" />
        <span className="truncate text-[13px] font-medium">{preset.title}</span>
        <span className="hidden text-[11px] text-faint sm:inline">· {preset.category}</span>
        {modified && (
          <span className="chip text-faint" title="You edited this example">
            <Pencil className="h-3 w-3" /> edited
          </span>
        )}
        <span className="ml-auto flex items-center gap-2">
          <span className="hidden text-[11px] text-faint md:inline">expected</span>
          <VerdictChip verdict={preset.expected_verdict} />
          <ChevronDown className={`h-4 w-4 text-faint transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {open && (
        <p className="animate-fade-in px-3 pb-3 text-[12.5px] leading-relaxed text-muted">
          <RichText text={preset.summary} />
        </p>
      )}
    </div>
  );
}
