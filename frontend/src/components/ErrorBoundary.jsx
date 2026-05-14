import React from "react";

/**
 * Top-level error boundary. Catches render-time exceptions so the page
 * never goes blank on the user. Also reports the error via the global
 * window.error path (handled by errorReporter.js).
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Re-throw on the global error path so our errorReporter logs it.
    // setTimeout breaks us out of React's error-handling context.
    setTimeout(() => {
      const e = new Error(error?.message || "React render error");
      e.stack = (error?.stack || "") + "\n--- componentStack ---\n" + (info?.componentStack || "");
      throw e;
    }, 0);
  }

  reset = () => this.setState({ hasError: false, error: null });

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div
        className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-100 p-8"
        data-testid="error-boundary-fallback"
      >
        <div className="max-w-md space-y-4 text-center">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-red-400">
            Runtime error
          </div>
          <div className="font-mono text-xs text-zinc-300 leading-relaxed border border-zinc-800 p-4 break-words text-left">
            {String(this.state.error?.message || this.state.error || "Unknown error")}
          </div>
          <button
            onClick={this.reset}
            className="font-mono text-[10px] uppercase tracking-[0.18em] border border-zinc-700 px-4 py-2 hover:bg-zinc-100 hover:text-zinc-950 transition-colors"
            data-testid="error-boundary-reset"
          >
            Try again
          </button>
          <div className="font-mono text-[9px] text-zinc-600">
            This error has been reported automatically.
          </div>
        </div>
      </div>
    );
  }
}
