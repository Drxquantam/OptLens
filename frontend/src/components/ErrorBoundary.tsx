import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertOctagon, RotateCcw } from 'lucide-react';

interface State {
  error: Error | null;
}

/** Keeps a rendering bug in one panel from blanking the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: unknown }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('OptLens panel crashed', error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey?: unknown }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="m-4 card flex items-start gap-3 p-5">
        <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-bad" />
        <div className="min-w-0">
          <h2 className="font-semibold">This view failed to render</h2>
          <p className="mt-1 break-words font-mono text-xs text-muted">{this.state.error.message}</p>
          <button className="btn-ghost mt-3 -ml-2.5" onClick={() => this.setState({ error: null })}>
            <RotateCcw className="h-3.5 w-3.5" /> Try again
          </button>
        </div>
      </div>
    );
  }
}
