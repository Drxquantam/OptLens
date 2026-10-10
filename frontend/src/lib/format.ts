import type { BuildOutcome } from '../types';

export const GROUP_LETTERS = 'ABCDEF';

/** Distinct, theme-friendly colours for behaviour groups (A is the majority). */
export const GROUP_STYLES = [
  'bg-ok/10 text-ok border-ok/30',
  'bg-warn/10 text-warn border-warn/30',
  'bg-bad/10 text-bad border-bad/30',
  'bg-accent/10 text-accent border-accent/30',
  'bg-neutral/10 text-neutral border-neutral/30',
  'bg-neutral/10 text-neutral border-neutral/30',
];

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return '–';
  if (ms < 1) return `${(ms * 1000).toFixed(0)} µs`;
  if (ms < 1000) return `${ms.toFixed(ms < 10 ? 1 : 0)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function optLabel(opt: string): string {
  return `-${opt}`;
}

export function compilerLabel(cc: string): string {
  return cc === 'gcc' ? 'GCC' : cc === 'clang' ? 'Clang' : cc;
}

export function buildLabel(b: Pick<BuildOutcome, 'compiler' | 'opt'>): string {
  return `${compilerLabel(b.compiler)} ${optLabel(b.opt)}`;
}

export function statusLabel(b: BuildOutcome): string {
  switch (b.status) {
    case 'ok':
      return b.exit_code === 0 ? 'ok' : `exit ${b.exit_code}`;
    case 'compile_error':
      return 'compile error';
    case 'timeout':
      return 'timeout';
    case 'crashed':
      return b.signal ?? 'crashed';
    case 'output_limit':
      return 'output limit';
  }
}

export function relativeTime(epochSeconds: number): string {
  const s = Math.max(0, Date.now() / 1000 - epochSeconds);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
