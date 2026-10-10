import type { LucideIcon } from 'lucide-react';
import { AlertOctagon, AlertTriangle, Bug, CheckCircle2, Clock, Dices, FileWarning, ServerCrash, Skull } from 'lucide-react';
import type { Verdict } from '../types';

export type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

export interface VerdictMeta {
  label: string;
  tone: Tone;
  icon: LucideIcon;
}

export const VERDICTS: Record<Verdict, VerdictMeta> = {
  MATCH: { label: 'Match', tone: 'ok', icon: CheckCircle2 },
  LATENT_UB: { label: 'Latent UB', tone: 'warn', icon: AlertTriangle },
  MISMATCH_UB: { label: 'Mismatch · UB', tone: 'warn', icon: AlertTriangle },
  MISMATCH_SUSPECTED_COMPILER_BUG: { label: 'Suspected compiler bug', tone: 'bad', icon: Bug },
  NONDETERMINISTIC: { label: 'Nondeterministic', tone: 'neutral', icon: Dices },
  COMPILE_ERROR: { label: 'Compile error', tone: 'neutral', icon: FileWarning },
  TIMEOUT: { label: 'Timeout', tone: 'neutral', icon: Clock },
  RUNTIME_ERROR: { label: 'Runtime error', tone: 'neutral', icon: Skull },
  INTERNAL_ERROR: { label: 'Sandbox error', tone: 'neutral', icon: ServerCrash },
};

export const SANDBOX_FAILURE: VerdictMeta = { label: 'Sandbox error', tone: 'neutral', icon: AlertOctagon };

/** Static class names per tone (spelled out so Tailwind's scanner keeps them). */
export const TONE = {
  ok: { text: 'text-ok', bg: 'bg-ok/10', border: 'border-ok/30', dot: 'bg-ok', ring: 'ring-ok/20' },
  warn: { text: 'text-warn', bg: 'bg-warn/10', border: 'border-warn/30', dot: 'bg-warn', ring: 'ring-warn/20' },
  bad: { text: 'text-bad', bg: 'bg-bad/10', border: 'border-bad/30', dot: 'bg-bad', ring: 'ring-bad/20' },
  neutral: {
    text: 'text-neutral',
    bg: 'bg-neutral/10',
    border: 'border-neutral/30',
    dot: 'bg-neutral',
    ring: 'ring-neutral/20',
  },
} as const;
