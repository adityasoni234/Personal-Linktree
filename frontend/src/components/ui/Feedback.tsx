/** Loading, empty and error states. */

import { AlertTriangle, Inbox, Loader2, RefreshCw, WifiOff } from 'lucide-react';

import type { ApiError } from '@/api/client';
import { cn } from '@/lib/utils';

import { Button } from './Button';

export function Spinner({ className, label = 'Loading' }: { className?: string; label?: string }) {
  return (
    <span role="status" className={cn('inline-flex items-center gap-2', className)}>
      <Loader2 className="h-4 w-4 animate-spin text-ieee-600" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('shimmer rounded-lg bg-navy-100', className)}
      aria-hidden="true"
    />
  );
}

/** Skeleton shaped like the content it replaces, to avoid layout shift. */
export function SkeletonCard() {
  return (
    <div className="card space-y-4 p-5">
      <div className="flex items-center gap-3">
        <Skeleton className="h-11 w-11 rounded-xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-4/5" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-xl" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function PageLoader({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
      <Loader2 className="h-7 w-7 animate-spin text-ieee-600" aria-hidden="true" />
      <p className="text-sm text-navy-500">{label}…</p>
    </div>
  );
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  secondaryAction?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-2xl border border-dashed border-navy-200 bg-surface-subtle/60 px-6 py-14 text-center',
        className,
      )}
    >
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-ieee-600 shadow-card">
        {icon ?? <Inbox className="h-6 w-6" aria-hidden="true" />}
      </span>
      <h3 className="text-base font-semibold text-navy-900">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-md text-sm text-navy-500 text-pretty">{description}</p>
      )}
      {(action || secondaryAction) && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}

interface ErrorStateProps {
  error: ApiError | Error | null;
  onRetry?: () => void;
  title?: string;
  className?: string;
}

export function ErrorState({ error, onRetry, title, className }: ErrorStateProps) {
  const isOffline =
    error && 'code' in error && (error as ApiError).code === 'NETWORK_ERROR';

  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center rounded-2xl border border-danger-100 bg-danger-50/50 px-6 py-12 text-center',
        className,
      )}
    >
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-danger-600 shadow-card">
        {isOffline ? (
          <WifiOff className="h-6 w-6" aria-hidden="true" />
        ) : (
          <AlertTriangle className="h-6 w-6" aria-hidden="true" />
        )}
      </span>
      <h3 className="text-base font-semibold text-navy-900">
        {title ?? (isOffline ? 'You appear to be offline' : 'Something went wrong')}
      </h3>
      <p className="mt-1.5 max-w-md text-sm text-navy-600 text-pretty">
        {error?.message ?? 'Please try again in a moment.'}
      </p>
      {error && 'requestId' in error && (error as ApiError).requestId && (
        <p className="mt-2 font-mono text-2xs text-navy-400">
          Reference: {(error as ApiError).requestId}
        </p>
      )}
      {onRetry && (
        <Button
          variant="outline"
          className="mt-5"
          onClick={onRetry}
          leftIcon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
        >
          Try again
        </Button>
      )}
    </div>
  );
}

/** Inline banner for contextual warnings (e.g. QR scannability). */
export function Callout({
  tone = 'info',
  title,
  children,
  icon,
  className,
}: {
  tone?: 'info' | 'warning' | 'danger' | 'success';
  title?: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  const tones = {
    info: 'border-ieee-100 bg-ieee-50/70 text-ieee-900',
    warning: 'border-warning-100 bg-warning-50/70 text-warning-700',
    danger: 'border-danger-100 bg-danger-50/70 text-danger-700',
    success: 'border-success-100 bg-success-50/70 text-success-700',
  };

  return (
    <div
      className={cn('rounded-xl border px-4 py-3 text-sm', tones[tone], className)}
      role={tone === 'danger' ? 'alert' : undefined}
    >
      <div className="flex gap-2.5">
        {icon && <span className="mt-0.5 shrink-0">{icon}</span>}
        <div className="min-w-0">
          {title && <p className="font-semibold">{title}</p>}
          <div className={cn(title && 'mt-0.5', 'text-pretty')}>{children}</div>
        </div>
      </div>
    </div>
  );
}
