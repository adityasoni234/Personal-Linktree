import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Link2, MousePointerClick, Search } from 'lucide-react';

import { groupsApi, linksApi } from '@/api/endpoints';
import type { GroupSummary, LinkItem } from '@/api/types';
import { LinkIcon } from '@/components/public/LinkIcon';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Badge,
  Card,
  CardBody,
  EmptyState,
  ErrorState,
  Input,
  LinkButton,
  Select,
  SkeletonTable,
} from '@/components/ui';
import { useDebounced, useDocumentTitle, useQuery } from '@/hooks';
import { formatNumber, prettyUrl } from '@/lib/utils';

interface Row extends LinkItem {
  groupName: string;
  groupSlug: string;
}

/**
 * Every link across every group the user can see — the fastest way to answer
 * "where is that Instagram link again?" without opening each group.
 */
export function LinksPage() {
  useDocumentTitle('Links');
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState('all');
  const debouncedSearch = useDebounced(search);

  const groupsQuery = useQuery(() => groupsApi.list({ limit: 100 }), []);
  const [rows, setRows] = useState<Row[]>([]);
  const [isLoadingLinks, setIsLoadingLinks] = useState(true);

  const groups: GroupSummary[] = useMemo(
    () => groupsQuery.data?.data ?? [],
    [groupsQuery.data],
  );

  useEffect(() => {
    if (groupsQuery.isLoading) return;
    if (groups.length === 0) {
      setRows([]);
      setIsLoadingLinks(false);
      return;
    }

    let cancelled = false;
    setIsLoadingLinks(true);

    // One request per group, in parallel — the API is intentionally scoped per
    // group so a single tenant-wide "all links" query cannot be abused.
    Promise.all(
      groups.map((group) =>
        linksApi
          .list(group.id)
          .then((links) =>
            links.map<Row>((link) => ({
              ...link,
              groupName: group.name,
              groupSlug: group.slug,
            })),
          )
          .catch(() => [] as Row[]),
      ),
    )
      .then((results) => {
        if (!cancelled) setRows(results.flat());
      })
      .finally(() => {
        if (!cancelled) setIsLoadingLinks(false);
      });

    return () => {
      cancelled = true;
    };
  }, [groups, groupsQuery.isLoading]);

  const filtered = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    return rows
      .filter((row) => (groupFilter === 'all' ? true : row.group_id === groupFilter))
      .filter(
        (row) =>
          !term ||
          row.title.toLowerCase().includes(term) ||
          row.url.toLowerCase().includes(term) ||
          row.groupName.toLowerCase().includes(term),
      )
      .sort((first, second) => second.click_count - first.click_count);
  }, [rows, groupFilter, debouncedSearch]);

  const isLoading = groupsQuery.isLoading || isLoadingLinks;

  return (
    <>
      <PageHeader
        title="Links"
        description="Every link across your groups, ranked by clicks."
      />

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <Input
          type="search"
          placeholder="Search links…"
          aria-label="Search links"
          leftIcon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          containerClassName="w-full sm:w-72"
        />
        <Select
          aria-label="Filter by group"
          options={[
            { value: 'all', label: 'All groups' },
            ...groups.map((group) => ({ value: group.id, label: group.name })),
          ]}
          value={groupFilter}
          onChange={(event) => setGroupFilter(event.target.value)}
          className="w-full sm:w-56"
        />
      </div>

      {groupsQuery.error ? (
        <ErrorState error={groupsQuery.error} onRetry={groupsQuery.refetch} />
      ) : isLoading ? (
        <Card>
          <CardBody>
            <SkeletonTable rows={6} />
          </CardBody>
        </Card>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<Link2 className="h-6 w-6" aria-hidden="true" />}
          title={rows.length === 0 ? 'No links yet' : 'No links match your filters'}
          description={
            rows.length === 0
              ? 'Links live inside groups. Open a group to add your first one.'
              : 'Try a different search term or clear the group filter.'
          }
          action={
            rows.length === 0 ? (
              <LinkButton to="/dashboard/groups">Go to groups</LinkButton>
            ) : undefined
          }
        />
      ) : (
        <Card>
          <div className="scroll-x">
            <table className="w-full min-w-[46rem] text-sm">
              <caption className="sr-only">All links across your groups</caption>
              <thead>
                <tr className="border-b border-navy-200/70 text-left text-xs text-navy-500">
                  <th scope="col" className="px-5 py-3 font-medium">Link</th>
                  <th scope="col" className="px-3 py-3 font-medium">Group</th>
                  <th scope="col" className="px-3 py-3 font-medium">Destination</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">Clicks</th>
                  <th scope="col" className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-navy-100 transition last:border-0 hover:bg-surface-subtle"
                  >
                    <th scope="row" className="px-5 py-3 text-left font-normal">
                      <span className="flex items-center gap-2.5">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ieee-50 text-ieee-600">
                          <LinkIcon name={row.icon} className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-navy-900">
                            {row.title}
                          </span>
                          {row.description && (
                            <span className="block truncate text-2xs text-navy-400">
                              {row.description}
                            </span>
                          )}
                        </span>
                      </span>
                    </th>
                    <td className="px-3 py-3">
                      <Link
                        to={`/dashboard/groups/${row.group_id}`}
                        className="text-navy-700 hover:text-ieee-700"
                      >
                        {row.groupName}
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="inline-flex items-center gap-1 font-mono text-2xs text-navy-500 hover:text-ieee-600"
                      >
                        {prettyUrl(row.url, 34)}
                        <ExternalLink className="h-3 w-3" aria-hidden="true" />
                      </a>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span className="inline-flex items-center gap-1.5 font-semibold tabular-nums text-navy-900">
                        <MousePointerClick
                          className="h-3.5 w-3.5 text-navy-300"
                          aria-hidden="true"
                        />
                        {formatNumber(row.click_count)}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <Badge tone={row.is_active ? 'success' : 'neutral'} dot size="sm">
                        {row.is_active ? 'Visible' : 'Hidden'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}

export default LinksPage;
