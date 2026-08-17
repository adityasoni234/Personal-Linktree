import { createPortal } from 'react-dom';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';

import { cn } from '@/lib/utils';
import { useToastStore, type ToastVariant } from '@/stores/toast';

const ICONS: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle2 className="h-5 w-5 text-success-600" aria-hidden="true" />,
  error: <AlertCircle className="h-5 w-5 text-danger-600" aria-hidden="true" />,
  warning: <AlertTriangle className="h-5 w-5 text-warning-600" aria-hidden="true" />,
  info: <Info className="h-5 w-5 text-ieee-600" aria-hidden="true" />,
};

const BORDERS: Record<ToastVariant, string> = {
  success: 'border-l-success-500',
  error: 'border-l-danger-500',
  warning: 'border-l-warning-500',
  info: 'border-l-ieee-500',
};

export function Toaster() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      // `polite` so a toast never interrupts what a screen reader is saying;
      // errors are still announced, just in turn.
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:right-0 sm:top-0 sm:items-end sm:justify-start"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role={toast.variant === 'error' ? 'alert' : 'status'}
          className={cn(
            'pointer-events-auto flex w-full max-w-sm animate-slide-in-right items-start gap-3',
            'rounded-xl border border-navy-200/70 border-l-4 bg-white p-3.5 shadow-panel',
            BORDERS[toast.variant],
          )}
        >
          <span className="mt-0.5 shrink-0">{ICONS[toast.variant]}</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-navy-900">{toast.title}</p>
            {toast.description && (
              <p className="mt-0.5 text-sm text-navy-600 text-pretty">{toast.description}</p>
            )}
            {toast.action && (
              <button
                type="button"
                onClick={() => {
                  toast.action?.onClick();
                  dismiss(toast.id);
                }}
                className="mt-2 text-sm font-semibold text-ieee-600 underline-offset-2 hover:underline"
              >
                {toast.action.label}
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => dismiss(toast.id)}
            aria-label="Dismiss notification"
            className="-mr-1 -mt-1 rounded-lg p-1 text-navy-400 transition hover:bg-navy-100 hover:text-navy-700"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>,
    document.body,
  );
}
