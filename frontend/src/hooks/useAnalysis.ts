import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api';
import type { JobInfo } from '../types';

export type RunState =
  | { phase: 'idle' }
  | { phase: 'submitting'; startedAt: number }
  | { phase: 'queued' | 'running'; jobId: string; position: number | null; startedAt: number }
  | { phase: 'done'; job: JobInfo }
  | { phase: 'failed'; error: string; job?: JobInfo };

const POLL_MS = 400;
const MAX_POLL_FAILURES = 5;

export function useAnalysis(onError: (message: string) => void) {
  const [state, setState] = useState<RunState>({ phase: 'idle' });
  const generation = useRef(0);

  const poll = useCallback(
    async (jobId: string, startedAt: number, gen: number) => {
      let failures = 0;
      while (generation.current === gen) {
        let job: JobInfo;
        try {
          job = await api.job(jobId);
          failures = 0;
        } catch (e) {
          if (generation.current !== gen) return;
          // Ride out brief proxy/network hiccups; the job keeps running server-side.
          const transient = !(e instanceof ApiError) || e.status === 0 || e.status >= 502;
          if (transient && ++failures <= MAX_POLL_FAILURES) {
            await new Promise((r) => setTimeout(r, POLL_MS * 2 ** failures));
            continue;
          }
          const msg = e instanceof ApiError ? e.message : 'Lost connection while waiting for the result';
          setState({ phase: 'failed', error: msg });
          onError(msg);
          return;
        }
        if (generation.current !== gen) return;
        if (job.status === 'done') {
          setState({ phase: 'done', job });
          return;
        }
        if (job.status === 'failed') {
          const msg = job.error ?? 'The sandbox failed to analyse this program';
          setState({ phase: 'failed', error: msg, job });
          onError(msg);
          return;
        }
        setState({ phase: job.status, jobId, position: job.queue_position, startedAt });
        await new Promise((r) => setTimeout(r, POLL_MS));
      }
    },
    [onError],
  );

  const run = useCallback(
    async (source: string, stdin: string, presetId: string | null) => {
      const gen = ++generation.current;
      const startedAt = Date.now();
      setState({ phase: 'submitting', startedAt });
      try {
        const accepted = await api.analyze(source, stdin, presetId);
        if (generation.current !== gen) return;
        setState({ phase: 'queued', jobId: accepted.job_id, position: accepted.queue_position, startedAt });
        await poll(accepted.job_id, startedAt, gen);
      } catch (e) {
        if (generation.current !== gen) return;
        const msg = e instanceof ApiError ? e.message : String(e);
        setState({ phase: 'failed', error: msg });
        onError(msg);
      }
    },
    [poll, onError],
  );

  /** Load a finished job (e.g. from history or a ?job= link). */
  const load = useCallback(
    async (jobId: string): Promise<JobInfo | null> => {
      const gen = ++generation.current;
      try {
        const job = await api.job(jobId);
        if (generation.current !== gen) return null;
        if (job.status === 'done') setState({ phase: 'done', job });
        else if (job.status === 'failed') setState({ phase: 'failed', error: job.error ?? 'failed', job });
        else void poll(jobId, Date.now(), gen);
        return job;
      } catch (e) {
        onError(e instanceof ApiError ? e.message : String(e));
        return null;
      }
    },
    [poll, onError],
  );

  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );

  const busy = state.phase === 'submitting' || state.phase === 'queued' || state.phase === 'running';
  return { state, run, load, busy };
}
