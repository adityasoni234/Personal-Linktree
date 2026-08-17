import { Activity, Building2, Database, Link2, Server, Users } from 'lucide-react';

import { adminApi } from '@/api/endpoints';
import { PageHeader } from '@/components/layout/DashboardLayout';
import { Callout, Card, CardBody, CardHeader, ErrorState, StatCard } from '@/components/ui';
import { useDocumentTitle, useQuery } from '@/hooks';
import { formatNumber } from '@/lib/utils';

export function SystemPage() {
  useDocumentTitle('System');
  const { data, error, isLoading, refetch } = useQuery(() => adminApi.systemStats(), []);

  return (
    <>
      <PageHeader
        title="System"
        description="Platform-wide totals. Visible to super administrators only."
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard
              label="Users"
              value={formatNumber(data?.users ?? 0)}
              icon={<Users className="h-4 w-4" aria-hidden="true" />}
              isLoading={isLoading}
            />
            <StatCard
              label="Organizations"
              value={formatNumber(data?.organizations ?? 0)}
              icon={<Building2 className="h-4 w-4" aria-hidden="true" />}
              isLoading={isLoading}
            />
            <StatCard
              label="Groups"
              value={formatNumber(data?.groups ?? 0)}
              icon={<Database className="h-4 w-4" aria-hidden="true" />}
              hint={`${data?.published_groups ?? 0} published`}
              isLoading={isLoading}
            />
            <StatCard
              label="Links"
              value={formatNumber(data?.links ?? 0)}
              icon={<Link2 className="h-4 w-4" aria-hidden="true" />}
              isLoading={isLoading}
            />
            <StatCard
              label="Events (30 days)"
              value={formatNumber(data?.events_last_30d ?? 0)}
              icon={<Activity className="h-4 w-4" aria-hidden="true" />}
              isLoading={isLoading}
            />
          </div>

          <Card>
            <CardHeader
              title="Operational notes"
              icon={<Server className="h-4 w-4" aria-hidden="true" />}
            />
            <CardBody className="space-y-4">
              <Callout tone="info" title="Health checks">
                <code className="font-mono">/health</code> reports process liveness;{' '}
                <code className="font-mono">/ready</code> additionally verifies the database
                and Redis and returns 503 when either is unavailable. Neither exposes
                hostnames, versions or connection strings.
              </Callout>
              <Callout tone="info" title="Rate limits">
                Limits are enforced in Redis with a sliding window, keyed by IP, by user and
                by endpoint. Authentication endpoints fail closed if Redis is unreachable, so
                a cache outage cannot become an open door for credential stuffing.
              </Callout>
              <Callout tone="info" title="Data retention">
                Expired sessions and used password-reset tokens are purged after 30 days.
                Analytics rows keep no raw IP address, and the visitor hash re-salts daily.
              </Callout>
            </CardBody>
          </Card>
        </div>
      )}
    </>
  );
}

export default SystemPage;
