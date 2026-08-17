import { useState } from 'react';
import { Eye, Monitor, MousePointerClick, QrCode, Users } from 'lucide-react';

import { analyticsApi, groupsApi } from '@/api/endpoints';
import type { TimeRange } from '@/api/types';
import { BarBreakdown, TrendChart } from '@/components/charts/TrendChart';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Card,
  CardBody,
  CardHeader,
  ErrorState,
  Select,
  Skeleton,
  StatCard,
  Tabs,
} from '@/components/ui';
import { useDocumentTitle, useQuery } from '@/hooks';
import { formatNumber } from '@/lib/utils';

const RANGES: { id: TimeRange; label: string }[] = [
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
  { id: '90d', label: '90 days' },
  { id: '12m', label: '12 months' },
];

export function AnalyticsPage() {
  useDocumentTitle('Analytics');
  const [range, setRange] = useState<TimeRange>('30d');
  const [groupId, setGroupId] = useState('all');

  const groupsQuery = useQuery(() => groupsApi.list({ limit: 100 }), []);
  const groups = groupsQuery.data?.data ?? [];

  const orgQuery = useQuery(
    () => analyticsApi.organization(range, 10),
    [range],
    { enabled: groupId === 'all' },
  );
  const groupQuery = useQuery(
    () => analyticsApi.group(groupId, range, 10),
    [groupId, range],
    { enabled: groupId !== 'all' },
  );

  const isGroupView = groupId !== 'all';
  const isLoading = isGroupView ? groupQuery.isLoading : orgQuery.isLoading;
  const error = isGroupView ? groupQuery.error : orgQuery.error;
  const refetch = isGroupView ? groupQuery.refetch : orgQuery.refetch;

  const totals = isGroupView ? groupQuery.data?.totals : orgQuery.data?.totals;
  const timeseries = isGroupView ? groupQuery.data?.timeseries : orgQuery.data?.timeseries;
  const devices = isGroupView ? groupQuery.data?.devices : orgQuery.data?.devices;
  const topLinks = isGroupView ? groupQuery.data?.top_links : orgQuery.data?.top_links;

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Scans, views and clicks — measured without storing raw IP addresses or tracking visitors across sites."
        actions={
          <>
            <Select
              aria-label="Scope"
              options={[
                { value: 'all', label: 'All groups' },
                ...groups.map((group) => ({ value: group.id, label: group.name })),
              ]}
              value={groupId}
              onChange={(event) => setGroupId(event.target.value)}
              className="w-48"
            />
            <Tabs
              tabs={RANGES}
              value={range}
              onChange={setRange}
              variant="pill"
              aria-label="Reporting period"
            />
          </>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard
              label="Page views"
              value={formatNumber(totals?.page_views ?? 0)}
              icon={<Eye className="h-4 w-4" aria-hidden="true" />}
              isLoading={isLoading}
            />
            <StatCard
              label="QR scans"
              value={formatNumber(totals?.qr_scans ?? 0)}
              icon={<QrCode className="h-4 w-4" aria-hidden="true" />}
              isLoading={isLoading}
            />
            <StatCard
              label="Link clicks"
              value={formatNumber(totals?.link_clicks ?? 0)}
              icon={<MousePointerClick className="h-4 w-4" aria-hidden="true" />}
              isLoading={isLoading}
            />
            <StatCard
              label="Unique visitors"
              value={formatNumber(totals?.unique_visitors ?? 0)}
              icon={<Users className="h-4 w-4" aria-hidden="true" />}
              hint="Daily salted hash"
              isLoading={isLoading}
            />
            <StatCard
              label="Click-through"
              value={`${totals?.click_through_rate ?? 0}%`}
              icon={<MousePointerClick className="h-4 w-4" aria-hidden="true" />}
              hint="Clicks per visit"
              isLoading={isLoading}
            />
          </div>

          <Card>
            <CardBody>
              {isLoading ? (
                <Skeleton className="h-72 w-full" />
              ) : (
                <TrendChart title="Traffic over time" data={timeseries ?? []} />
              )}
            </CardBody>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="Top links"
                description="Ranked by clicks in this period"
                icon={<MousePointerClick className="h-4 w-4" aria-hidden="true" />}
              />
              <CardBody>
                {isLoading ? (
                  <div className="space-y-4">
                    {[0, 1, 2, 3].map((index) => (
                      <Skeleton key={index} className="h-8 w-full" />
                    ))}
                  </div>
                ) : (
                  <BarBreakdown
                    items={topLinks ?? []}
                    emptyMessage="No link clicks recorded yet."
                  />
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Devices"
                description="What visitors are using"
                icon={<Monitor className="h-4 w-4" aria-hidden="true" />}
              />
              <CardBody>
                {isLoading ? (
                  <div className="space-y-4">
                    {[0, 1, 2].map((index) => (
                      <Skeleton key={index} className="h-8 w-full" />
                    ))}
                  </div>
                ) : (
                  <BarBreakdown
                    items={devices ?? []}
                    valueLabel="visits"
                    emptyMessage="No visits recorded yet."
                  />
                )}
              </CardBody>
            </Card>

            {isGroupView && (
              <>
                <Card>
                  <CardHeader title="Browsers" />
                  <CardBody>
                    <BarBreakdown
                      items={groupQuery.data?.browsers ?? []}
                      valueLabel="visits"
                      emptyMessage="No visits recorded yet."
                    />
                  </CardBody>
                </Card>
                <Card>
                  <CardHeader
                    title="Referrers"
                    description="Domain only — full URLs are never stored"
                  />
                  <CardBody>
                    <BarBreakdown
                      items={groupQuery.data?.referrers ?? []}
                      valueLabel="visits"
                      emptyMessage="Most visitors arrive directly or by QR code."
                    />
                  </CardBody>
                </Card>
              </>
            )}

            {!isGroupView && (
              <Card className="lg:col-span-2">
                <CardHeader
                  title="Top groups"
                  description="Ranked by views and scans"
                  icon={<Users className="h-4 w-4" aria-hidden="true" />}
                />
                <CardBody>
                  <BarBreakdown
                    items={orgQuery.data?.top_groups ?? []}
                    valueLabel="visits"
                    emptyMessage="No traffic recorded yet."
                  />
                </CardBody>
              </Card>
            )}
          </div>

          <p className="px-1 text-2xs text-navy-500">
            Visitor counts use a salted hash that rotates every day, so the same person on
            two days is counted twice rather than being trackable over time. No raw IP
            address is ever stored.
          </p>
        </div>
      )}
    </>
  );
}

export default AnalyticsPage;
