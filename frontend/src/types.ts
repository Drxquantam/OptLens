// Mirrors backend/optlens/models.py (public API schema).

export type Verdict =
  | 'MATCH'
  | 'LATENT_UB'
  | 'MISMATCH_UB'
  | 'MISMATCH_SUSPECTED_COMPILER_BUG'
  | 'NONDETERMINISTIC'
  | 'COMPILE_ERROR'
  | 'TIMEOUT'
  | 'RUNTIME_ERROR'
  | 'INTERNAL_ERROR';

export type BuildStatus = 'ok' | 'compile_error' | 'timeout' | 'crashed' | 'output_limit';

export interface BuildOutcome {
  id: string;
  compiler: string;
  opt: string;
  status: BuildStatus;
  compile_ok: boolean;
  compile_command: string;
  compile_stderr: string;
  compile_ms: number;
  exit_code: number | null;
  signal: string | null;
  stdout: string;
  stdout_truncated: boolean;
  stderr: string;
  output_hash: string | null;
  runtime_ms: number | null;
  group: number | null;
  deterministic: boolean | null;
  rerun_count: number;
  asm: string | null;
  asm_truncated: boolean;
  asm_instructions: number | null;
}

export interface Finding {
  sanitizer: 'UBSan' | 'ASan' | 'MSan' | 'compiler-warning';
  kind: string;
  message: string;
  line: number | null;
  column: number | null;
}

export interface SanitizerOutcome {
  name: string;
  compiled: boolean;
  compile_stderr: string;
  exit_code: number | null;
  signal: string | null;
  timed_out: boolean;
  report: string;
  findings: Finding[];
}

export interface Remark {
  kind: 'passed' | 'missed' | 'analysis';
  pass_name: string;
  message: string;
  line: number | null;
  column: number | null;
}

export interface VerdictInfo {
  verdict: Verdict;
  title: string;
  explanation: string;
  details: string[];
  evidence: Finding[];
  groups: string[][];
}

export interface AnalysisResult {
  verdict: VerdictInfo;
  builds: BuildOutcome[];
  sanitizers: SanitizerOutcome[];
  remarks: Remark[];
  remarks_truncated: boolean;
  warnings: Finding[];
  toolchain: Record<string, string>;
  limits: Record<string, number>;
}

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

export interface JobInfo {
  id: string;
  status: JobStatus;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  queue_position: number | null;
  preset_id: string | null;
  source: string | null;
  stdin: string | null;
  result: AnalysisResult | null;
  error: string | null;
}

export interface Preset {
  id: string;
  title: string;
  category: string;
  summary: string;
  expected_verdict: Verdict;
  source: string;
  stdin: string;
}

export interface HistoryItem {
  id: string;
  created_at: number;
  verdict: Verdict;
  preset_id: string | null;
  source_preview: string;
}

export interface Health {
  status: 'ok' | 'degraded';
  docker: boolean;
  sandbox_image: boolean;
  image: string;
  workers: number;
  queued: number;
  running: number;
}
