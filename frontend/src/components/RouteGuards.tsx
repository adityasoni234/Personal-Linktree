/**
 * Client-side route protection.
 *
 * This is a *user-experience* control, not a security boundary: it decides what
 * to render, not what the caller is allowed to do. Every endpoint behind these
 * routes re-checks permissions on the server, so bypassing this in devtools
 * gains an attacker nothing.
 */

import { Navigate, Outlet, useLocation } from 'react-router-dom';

import type { Role } from '@/api/types';
import { PageLoader } from '@/components/ui';
import { useAuthStore } from '@/stores/auth';

export function RequireAuth() {
  const status = useAuthStore((state) => state.status);
  const location = useLocation();

  if (status === 'loading') return <PageLoader label="Checking your session" />;

  if (status !== 'authenticated') {
    // Remember where the user was headed so sign-in can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }

  return <Outlet />;
}

export function RequireRole({ roles }: { roles: Role[] }) {
  const user = useAuthStore((state) => state.user);
  const status = useAuthStore((state) => state.status);

  if (status === 'loading') return <PageLoader />;
  if (status !== 'authenticated') return <Navigate to="/login" replace />;

  if (!user || !roles.includes(user.effective_role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Outlet />;
}

export function RedirectIfAuthenticated() {
  const status = useAuthStore((state) => state.status);
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;

  if (status === 'loading') return <PageLoader />;
  if (status === 'authenticated') return <Navigate to={from ?? '/dashboard'} replace />;

  return <Outlet />;
}
