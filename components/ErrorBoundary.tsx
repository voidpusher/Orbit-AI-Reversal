"use client";

import { Component, type ReactNode } from "react";
import { captureException } from "@/lib/observability";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

/**
 * Top-level error boundary: catches render/runtime errors anywhere in the tree,
 * reports them via captureException (Sentry when configured), and shows a calm
 * recovery screen instead of a white page.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: unknown): State {
    return { hasError: true, message: error instanceof Error ? error.message : "Something went wrong" };
  }

  componentDidCatch(error: unknown, info: unknown): void {
    captureException(error, { componentStack: (info as { componentStack?: string })?.componentStack });
  }

  private reset = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <main className="crash-page">
        <div className="crash-card">
          <span className="crash-mark">!</span>
          <h1>Something went wrong</h1>
          <p>An unexpected error occurred. The issue has been logged — you can retry or head back home.</p>
          <div className="crash-actions">
            <button className="button primary" onClick={this.reset}>Try again</button>
            <a className="button ghost" href="/">Go home</a>
          </div>
        </div>
      </main>
    );
  }
}
