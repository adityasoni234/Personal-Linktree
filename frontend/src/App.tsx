import { Suspense, lazy, useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { RedirectIfAuthenticated, RequireAuth, RequireRole } from '@/components/RouteGuards';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { PageLoader, Toaster } from '@/components/ui';
import { useAuthStore } from '@/stores/auth';

// Public routes load eagerly — they are the first paint for most visitors.
import { LandingPage } from '@/pages/Landing';
import { LoginPage } from '@/pages/auth/Login';
import { PublicGroupPage } from '@/pages/PublicGroup';

// Everything behind the sign-in wall is code-split, so a visitor scanning a QR
// code never downloads the dashboard.
const RegisterPage = lazy(() => import('@/pages/auth/Register'));
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPassword'));
const ResetPasswordPage = lazy(() => import('@/pages/auth/ResetPassword'));

const OverviewPage = lazy(() => import('@/pages/dashboard/Overview'));
const GroupsPage = lazy(() => import('@/pages/dashboard/Groups'));
const LinksPage = lazy(() => import('@/pages/dashboard/Links'));
const QrCodesPage = lazy(() => import('@/pages/dashboard/QrCodes'));
const AnalyticsPage = lazy(() => import('@/pages/dashboard/Analytics'));
const ProfilePage = lazy(() => import('@/pages/dashboard/Profile'));
const SettingsPage = lazy(() => import('@/pages/dashboard/Settings'));
const GroupBuilderPage = lazy(() => import('@/pages/builder/GroupBuilder'));

const AdminUsersPage = lazy(() => import('@/pages/admin/Users'));
const AuditLogPage = lazy(() => import('@/pages/admin/AuditLog'));
const SystemPage = lazy(() => import('@/pages/admin/System'));

const NotFoundPage = lazy(() => import('@/pages/NotFound'));

export function App() {
  const bootstrap = useAuthStore((state) => state.bootstrap);

  useEffect(() => {
    // Exchange the HttpOnly refresh cookie for an access token on first paint.
    void bootstrap();
  }, [bootstrap]);

  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* ---- Public ------------------------------------------------- */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/g/:slug" element={<PublicGroupPage />} />

          {/* ---- Authentication ---------------------------------------- */}
          <Route element={<RedirectIfAuthenticated />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
          </Route>

          {/* ---- Dashboard --------------------------------------------- */}
          <Route element={<RequireAuth />}>
            <Route element={<DashboardLayout />}>
              <Route path="/dashboard" element={<OverviewPage />} />
              <Route path="/dashboard/groups" element={<GroupsPage />} />
              <Route path="/dashboard/groups/new" element={<GroupBuilderPage />} />
              <Route path="/dashboard/groups/:groupId" element={<GroupBuilderPage />} />
              <Route path="/dashboard/links" element={<LinksPage />} />
              <Route path="/dashboard/qr-codes" element={<QrCodesPage />} />
              <Route path="/dashboard/analytics" element={<AnalyticsPage />} />
              <Route path="/dashboard/profile" element={<ProfilePage />} />
              <Route path="/dashboard/settings" element={<SettingsPage />} />

              {/* ---- Administration ------------------------------------ */}
              <Route element={<RequireRole roles={['ADMIN', 'SUPER_ADMIN']} />}>
                <Route path="/admin/users" element={<AdminUsersPage />} />
                <Route path="/admin/audit-logs" element={<AuditLogPage />} />
              </Route>
              <Route element={<RequireRole roles={['SUPER_ADMIN']} />}>
                <Route path="/admin/system" element={<SystemPage />} />
              </Route>
              <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>

      <Toaster />
    </ErrorBoundary>
  );
}
