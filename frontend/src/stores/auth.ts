/**
 * Authentication state.
 *
 * The access token is held in this store — in memory, for the lifetime of the
 * tab — and is deliberately never persisted. On a page reload the app calls
 * `bootstrap()`, which exchanges the HttpOnly refresh cookie for a fresh access
 * token. That means a stolen `localStorage` dump contains no credentials.
 */

import { create } from 'zustand';

import { configureAuthBridge } from '@/api/client';
import { authApi } from '@/api/endpoints';
import type { AuthSession, Role, UserProfile } from '@/api/types';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthState {
  status: AuthStatus;
  user: UserProfile | null;
  accessToken: string | null;
  expiresAt: number | null;

  bootstrap: () => Promise<void>;
  signIn: (email: string, password: string, rememberMe?: boolean) => Promise<UserProfile>;
  signUp: (payload: {
    email: string;
    full_name: string;
    password: string;
    organization_slug?: string;
  }) => Promise<UserProfile>;
  signOut: (options?: { everywhere?: boolean }) => Promise<void>;
  setSession: (session: AuthSession) => void;
  setUser: (user: UserProfile) => void;
  clear: () => void;
  hasPermission: (permission: string) => boolean;
  hasRole: (...roles: Role[]) => boolean;
}

// Refresh this long before the token actually expires, so an in-flight request
// never races the expiry.
const REFRESH_MARGIN_MS = 60_000;
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Single-flight guard for `bootstrap()`.
 *
 * React StrictMode runs mount effects twice in development, and a user can open
 * two tabs at once. Without this, two refreshes would race with the same
 * rotating token — which the server is right to treat as suspicious.
 */
let bootstrapPromise: Promise<void> | null = null;

function clearRefreshTimer(): void {
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: 'loading',
  user: null,
  accessToken: null,
  expiresAt: null,

  setSession: (session) => {
    const expiresAt = Date.now() + session.expires_in * 1000;
    set({
      status: 'authenticated',
      user: session.user,
      accessToken: session.access_token,
      expiresAt,
    });

    clearRefreshTimer();
    const delay = Math.max(5_000, session.expires_in * 1000 - REFRESH_MARGIN_MS);
    refreshTimer = setTimeout(() => {
      void authApi
        .refresh()
        .then((next) => get().setSession(next))
        .catch(() => get().clear());
    }, delay);
  },

  setUser: (user) => set({ user }),

  clear: () => {
    clearRefreshTimer();
    set({ status: 'anonymous', user: null, accessToken: null, expiresAt: null });
  },

  bootstrap: async () => {
    if (bootstrapPromise) return bootstrapPromise;

    bootstrapPromise = (async () => {
      try {
        const session = await authApi.refresh();
        get().setSession(session);
      } catch {
        // No valid refresh cookie: a normal first visit, not an error.
        set({ status: 'anonymous', user: null, accessToken: null, expiresAt: null });
      } finally {
        bootstrapPromise = null;
      }
    })();

    return bootstrapPromise;
  },

  signIn: async (email, password, rememberMe = false) => {
    const session = await authApi.login({ email, password, remember_me: rememberMe });
    get().setSession(session);
    return session.user;
  },

  signUp: async (payload) => {
    const session = await authApi.register(payload);
    get().setSession(session);
    return session.user;
  },

  signOut: async (options) => {
    try {
      if (options?.everywhere) {
        await authApi.logoutAll();
      } else {
        await authApi.logout();
      }
    } catch {
      // Even if the call fails, drop local state — the cookie is cleared by the
      // server on any successful path and the token expires within minutes.
    } finally {
      get().clear();
    }
  },

  hasPermission: (permission) => get().user?.permissions.includes(permission) ?? false,

  hasRole: (...roles) => {
    const role = get().user?.effective_role;
    return role ? roles.includes(role) : false;
  },
}));

// Wire the HTTP client to this store without creating an import cycle.
configureAuthBridge({
  getAccessToken: () => useAuthStore.getState().accessToken,
  onSessionRefreshed: (session) => useAuthStore.getState().setSession(session as AuthSession),
  onSessionLost: () => useAuthStore.getState().clear(),
});

/** Convenience selectors — components subscribe to the narrowest slice. */
export const useUser = () => useAuthStore((state) => state.user);
export const useAuthStatus = () => useAuthStore((state) => state.status);
export const useIsAuthenticated = () =>
  useAuthStore((state) => state.status === 'authenticated');
