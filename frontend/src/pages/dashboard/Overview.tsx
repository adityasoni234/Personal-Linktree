import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  BarChart3,
  Eye,
  Link2,
  MousePointerClick,
  Plus,
  QrCode,
  Users,
} from 'lucide-react';

import { analyticsApi } from '@/api/endpoints';
import type { TimeRange } from '@/api/types';
import { TrendChart } from '@/components/charts/TrendChart';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  LinkButton,
  Skeleton,
  StatCard,
  StatusBadge,
  Tabs,
} from '@/components/ui';
import { useDocumentTitle, useQuery } from '@/hooks';
import { formatNumber, formatRelativeTime } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';

const RANGES: { id: TimeRange; label: string }[] = [
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
  { id: '90d', label: '90 days' },
];

export function OverviewPage() {
  useDocumentTitle('Overview');
  const user = useAuthStore((state) => state.user);
  const [range, setRange] = useState<TimeRange>('30d');

  const { data, error, isLoading, refetch } = useQuery(
    () => analyticsApi.overview(range),
    [range],
  );

  const firstName = user?.full_name.split(' ')[0] ?? 'there';

  return (
    <>
      <PageHeader
        title={`Welcome back, ${firstName}`}
        description="Your organization's pages, links and QR performance at a glance."
        actions={
          <>
            <Tabs
              tabs={RANGES}
              value={range}
              onChange={setRange}
              variant="pill"
              aria-label="Reporting period"
            />
            <LinkButton to="/dashboard/groups/new" leftIcon={<Plus className="h-4 w-4" />}>
              New group
            </LinkButton>
          </>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Groups"
              value={formatNumber(data?.total_groups ?? 0)}
              icon={<Users className="h-4 w-4" aria-hidden="true" />}
              hint={`${data?.published_groups ?? 0} published`}
              isLoading={isLoading}
            />
            <StatCard
              label="Links"
              value={formatNumber(data?.total_links ?? 0)}
              icon={<Link2 className="h-4 w-4" aria-hidden="true" />}
              hint="Across all groups"
              isLoading={isLoading}
            />
            <StatCard
              label="QR scans"
              value={formatNumber(data?.total_qr_scans ?? 0)}
              icon={<QrCode className="h-4 w-4" aria-hidden="true" />}
              hint="All time"
              isLoading={isLoading}
            />
            <StatCard
              label="Page views"
              value={formatNumber(data?.total_page_views ?? 0)}
              icon={<Eye className="h-4 w-4" aria-hidden="true" />}
              hint="All time"
              isLoading={isLoading}
            />
          </div>

          <Card>
            <CardBody>
              {isLoading ? (
                <Skeleton className="h-72 w-full" />
              ) : (
                <TrendChart
                  title={`Traffic — last ${RANGES.find((item) => item.id === range)?.label}`}
                  data={data?.timeseries ?? []}
                />
              )}
            </CardBody>
          </Card>

          <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
            <Card>
              <CardHeader
                title="Your groups"
                description="Published pages and their traffic"
                icon={<Users className="h-4 w-4" aria-hidden="true" />}
                action={
                  <Link
                    to="/dashboard/groups"
                    className="inline-flex items-center gap-1 text-sm font-medium text-ieee-600 hover:underline"
                  >
                    View all
                    <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </Link>
                }
              />
              <CardBody className="p-0">
                {isLoading ? (
                  <div className="space-y-3 p-5">
                    {[0, 1, 2].map((index) => (
                      <Skeleton key={index} className="h-12 w-full" />
                    ))}
                  </div>
                ) : (data?.groups.length ?? 0) === 0 ? (
                  <EmptyState
                    className="m-5 border-0 bg-transparent py-10"
                    icon={<Users className="h-6 w-6" aria-hidden="true" />}
                    title="No groups yet"
                    description="Create your first group to get a public page and a QR code."
                    action={
                      <LinkButton
                        to="/dashboard/groups/new"
                        leftIcon={<Plus className="h-4 w-4" />}
                      >
                        Create a group
                      </LinkButton>
                    }
                  />
                ) : (
                  <div className="scroll-x">
                    <table className="w-full min-w-[36rem] text-sm">
                      <caption className="sr-only">Groups and their traffic</caption>
                      <thead>
                        <tr className="border-b border-navy-200/70 text-left text-xs text-navy-500">
                          <th scope="col" className="px-5 py-2.5 font-medium">Group</th>
                          <th scope="col" className="px-3 py-2.5 text-right font-medium">Links</th>
                          <th scope="col" className="px-3 py-2.5 text-right font-medium">Views</th>
                          <th scope="col" className="px-3 py-2.5 text-right font-medium">Scans</th>
                          <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                          <th scope="col" className="px-5 py-2.5 font-medium">Updated</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data?.groups.map((group) => (
                          <tr
                            key={group.id}
                            className="border-b border-navy-100 transition last:border-0 hover:bg-surface-subtle"
                          >
                            <th scope="row" className="px-5 py-3 text-left font-normal">
                              <Link
                                to={`/dashboard/groups/${group.id}`}
                                className="font-medium text-navy-900 hover:text-ieee-700"
                              >
                                {group.name}
                              </Link>
                              <span className="block text-2xs text-navy-400">/g/{group.slug}</span>
                            </th>
                            <td className="px-3 py-3 text-right tabular-nums text-navy-700">
                              {group.links}
                            </td>
                            <td className="px-3 py-3 text-right tabular-nums text-navy-700">
                              {formatNumber(group.page_views)}
                            </td>
                            <td className="px-3 py-3 text-right tabular-nums text-navy-700">
                              {formatNumber(group.qr_scans)}
                            </td>
                            <td className="px-3 py-3">
                              <StatusBadge status={group.status} />
                            </td>
                            <td className="px-5 py-3 text-navy-500">
                              {formatRelativeTime(group.updated_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Recent activity"
                description="Who changed what"
                icon={<BarChart3 className="h-4 w-4" aria-hidden="true" />}
              />
              <CardBody>
                {isLoading ? (
                  <div className="space-y-3">
                    {[0, 1, 2, 3].map((index) => (
                      <Skeleton key={index} className="h-10 w-full" />
                    ))}
                  </div>
                ) : (data?.recent_activity.length ?? 0) === 0 ? (
                  <p className="py-8 text-center text-sm text-navy-500">
                    Nothing has happened yet.
                  </p>
                ) : (
                  <ol className="space-y-3.5">
                    {data?.recent_activity.map((entry) => (
                      <li key={entry.id} className="flex gap-3">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ieee-500" />
                        <div className="min-w-0">
                          <p className="text-sm text-navy-800">
                            <span className="font-medium">
                              {entry.actor_name ?? 'Someone'}
                            </span>{' '}
                            {entry.description}
                          </p>
                          <p className="text-2xs text-navy-400">
                            {formatRelativeTime(entry.created_at)}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </CardBody>
            </Card>
          </div>

          <Card className="bg-navy-900 text-white">
            <CardBody className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10">
                  <MousePointerClick className="h-5 w-5" aria-hidden="true" />
                </span>
                <div>
                  <p className="font-medium">Print once, change forever</p>
                  <p className="mt-0.5 max-w-xl text-sm text-navy-200 text-pretty">
                    Every QR code points at the group page, not at a specific link — so you
                    can swap the links behind it any time without reprinting a poster.
                  </p>
                </div>
              </div>
              <Badge tone="brand" className="bg-white/10 text-white ring-white/20">
                Dynamic QR
              </Badge>
            </CardBody>
          </Card>
        </div>
      )}
    </>
  );
}

export default OverviewPage;
