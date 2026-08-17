import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

import { Button } from '@/components/ui';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

/**
 * Catches render-time crashes so a single broken component does not blank the
 * whole app. The technical message is only shown in development — in production
 * it would leak implementation detail to the user for no benefit.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Replace with a real error reporter (Sentry, GlitchTip) in production.
    console.error('Unhandled UI error', error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-subtle px-6">
        <div className="w-full max-w-md rounded-2xl border border-navy-200/70 bg-white p-8 text-center shadow-card">
          <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-danger-50 text-danger-600">
            <AlertTriangle className="h-6 w-6" aria-hidden="true" />
          </span>
          <h1 className="font-display text-xl font-semibold text-navy-900">
            Something went wrong
          </h1>
          <p className="mt-2 text-sm text-navy-600 text-pretty">
            The page could not be displayed. Reloading usually fixes it.
          </p>
          {import.meta.env.DEV && this.state.message && (
            <pre className="mt-4 overflow-x-auto rounded-lg bg-navy-900 p-3 text-left text-2xs text-navy-100">
              {this.state.message}
            </pre>
          )}
          <div className="mt-6 flex justify-center gap-2">
            <Button onClick={() => window.location.reload()}>Reload page</Button>
            <Button variant="outline" onClick={() => window.location.assign('/dashboard')}>
              Go to dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }
}
