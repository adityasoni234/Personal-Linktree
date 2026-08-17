import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';

import { LinkButton } from '@/components/ui';
import { useDocumentTitle } from '@/hooks';
import { useIsAuthenticated } from '@/stores/auth';

export function NotFoundPage() {
  useDocumentTitle('Page not found');
  const isAuthenticated = useIsAuthenticated();

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-subtle px-6">
      <div className="w-full max-w-md text-center">
        <span className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-ieee-600 shadow-card">
          <Compass className="h-7 w-7" aria-hidden="true" />
        </span>
        <p className="font-display text-5xl font-semibold text-navy-900">404</p>
        <h1 className="mt-3 font-display text-xl font-semibold text-navy-900">
          We could not find that page
        </h1>
        <p className="mt-2 text-sm text-navy-600 text-pretty">
          The address may have changed, or the group page may not be published. Group pages
          live at <code className="font-mono text-navy-800">/g/group-name</code>.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-2">
          <LinkButton to={isAuthenticated ? '/dashboard' : '/'}>
            {isAuthenticated ? 'Back to dashboard' : 'Back to home'}
          </LinkButton>
          {!isAuthenticated && (
            <Link
              to="/login"
              className="inline-flex h-10 items-center rounded-xl border border-navy-200 bg-white px-4 text-sm font-medium text-navy-800 shadow-card hover:bg-surface-subtle"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

export default NotFoundPage;
