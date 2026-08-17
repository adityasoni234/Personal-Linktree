/** Toast notifications. */

import { create } from 'zustand';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  /** Milliseconds before auto-dismiss; 0 keeps it until dismissed. */
  duration: number;
  action?: { label: string; onClick: () => void };
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, 'id' | 'duration'> & { duration?: number }) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

const DEFAULT_DURATION = 5000;
// Errors stay longer: they usually need reading, sometimes acting on.
const ERROR_DURATION = 8000;
const MAX_VISIBLE = 4;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  push: ({ duration, ...toast }) => {
    const id = crypto.randomUUID();
    const resolved =
      duration ?? (toast.variant === 'error' ? ERROR_DURATION : DEFAULT_DURATION);

    set((state) => ({
      toasts: [...state.toasts, { ...toast, id, duration: resolved }].slice(-MAX_VISIBLE),
    }));

    if (resolved > 0) {
      setTimeout(() => {
        set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) }));
      }, resolved);
    }
    return id;
  },

  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),

  clear: () => set({ toasts: [] }),
}));

export const toast = {
  success: (title: string, description?: string) =>
    useToastStore.getState().push({ variant: 'success', title, description }),
  error: (title: string, description?: string) =>
    useToastStore.getState().push({ variant: 'error', title, description }),
  warning: (title: string, description?: string) =>
    useToastStore.getState().push({ variant: 'warning', title, description }),
  info: (title: string, description?: string) =>
    useToastStore.getState().push({ variant: 'info', title, description }),
};
