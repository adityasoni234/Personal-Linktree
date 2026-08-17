import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Archive,
  ArchiveRestore,
  Copy,
  ExternalLink,
  Eye,
  Globe,
  Link2,
  Pencil,
  Plus,
  QrCode,
  Search,
  Trash2,
  Users,
} from 'lucide-react';

import { groupsApi } from '@/api/endpoints';
import type { GroupSummary } from '@/api/types';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  IconButton,
  Input,
  LinkButton,
  Menu,
  SkeletonCard,
  StatusBadge,
  Tabs,
} from '@/components/ui';
import { useCopyToClipboard, useDebounced, useDocumentTitle, useQuery } from '@/hooks';
import { formatNumber, formatRelativeTime } from '@/lib/utils';
import { toast } from '@/stores/toast';

type StatusFilter = 'all' | 'published' | 'draft' | 'archived';

const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'published', label: 'Published' },
  { id: 'draft', label: 'Drafts' },
  { id: 'archived', label: 'Archived' },
];

function GroupCard({
  group,
  onArchive,
  onRestore,
  onDelete,
  onDuplicate,
}: {
  group: GroupSummary;
  onArchive: (group: GroupSummary) => void;
  onRestore: (group: GroupSummary) => void;
  onDelete: (group: GroupSummary) => void;
  onDuplicate: (group: GroupSummary) => void;
}) {
  const { copied, copy } = useCopyToClipboard();
  const status = group.is_archived ? 'archived' : group.is_published ? 'published' : 'draft';

  return (
    <Card interactive className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          {group.logo_url ? (
            <img
              src={group.logo_url}
              alt=""
              className="h-11 w-11 shrink-0 rounded-xl object-cover ring-1 ring-navy-200"
              loading="lazy"
            />
          ) : (
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-ieee-50 text-ieee-600">
              <Users className="h-5 w-5" aria-hidden="true" />
            </span>
          )}
          <div className="min-w-0">
            <Link
              to={`/dashboard/groups/${group.id}`}
              className="block truncate font-semibold text-navy-900 hover:text-ieee-700"
            >
              {group.name}
            </Link>
            <button
              type="button"
              onClick={() => {
                void copy(group.public_url).then((ok) =>
                  ok
                    ? toast.success('Link copied', group.public_url)
                    : toast.error('Could not copy the link'),
                );
              }}
              className="mt-0.5 truncate font-mono text-2xs text-navy-400 transition hover:text-ieee-600"
              title="Copy public link"
            >
              /g/{group.slug} {copied && '· copied'}
            </button>
          </div>
        </div>

        <Menu
          items={[
            {
              label: 'Edit',
              icon: <Pencil className="h-4 w-4" />,
              onSelect: () => window.location.assign(`/dashboard/groups/${group.id}`),
            },
            {
              label: 'Duplicate',
              icon: <Copy className="h-4 w-4" />,
              onSelect: () => onDuplicate(group),
            },
            group.is_archived
              ? {
                  label: 'Restore',
                  icon: <ArchiveRestore className="h-4 w-4" />,
                  onSelect: () => onRestore(group),
                }
              : {
                  label: 'Archive',
                  icon: <Archive className="h-4 w-4" />,
                  onSelect: () => onArchive(group),
                },
            {
              label: 'Delete',
              icon: <Trash2 className="h-4 w-4" />,
              tone: 'danger',
              separated: true,
              onSelect: () => onDelete(group),
            },
          ]}
        />
      </div>

      {group.description && (
        <p className="mt-3 line-clamp-2 text-sm text-navy-500 text-pretty">
          {group.description}
        </p>
      )}

      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-navy-100 pt-4 text-center">
        {[
          { label: 'Links', value: group.stats.link_count, icon: Link2 },
          { label: 'Views', value: group.stats.page_views, icon: Eye },
          { label: 'Scans', value: group.stats.qr_scans, icon: QrCode },
        ].map((stat) => (
          <div key={stat.label}>
            <dt className="flex items-center justify-center gap-1 text-2xs text-navy-400">
              <stat.icon className="h-3 w-3" aria-hidden="true" />
              {stat.label}
            </dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-navy-900">
              {formatNumber(stat.value)}
            </dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={status} />
          <span className="text-2xs text-navy-400">
            {formatRelativeTime(group.updated_at)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {group.is_published && (
            <IconButton
              size="sm"
              label={`Open ${group.name} public page`}
              icon={<ExternalLink className="h-4 w-4" />}
              onClick={() => window.open(group.public_url, '_blank', 'noopener,noreferrer')}
            />
          )}
          <LinkButton to={`/dashboard/groups/${group.id}`} size="sm" variant="outline">
            Edit
          </LinkButton>
        </div>
      </div>
    </Card>
  );
}

export function GroupsPage() {
  useDocumentTitle('Groups');
  const navigate = useNavigate();

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  const [confirmDelete, setConfirmDelete] = useState<GroupSummary | null>(null);
  const [isPending, setIsPending] = useState(false);

  const { data, error, isLoading, refetch } = useQuery(
    () => groupsApi.list({ page, limit: 12, search: debouncedSearch, status }),
    [page, debouncedSearch, status],
  );

  const run = async (action: () => Promise<unknown>, message: string) => {
    setIsPending(true);
    try {
      await action();
      toast.success(message);
      await refetch();
    } catch (caught) {
      toast.error('Action failed', caught instanceof Error ? caught.message : undefined);
    } finally {
      setIsPending(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Groups"
        description="Each group is a public page with its own links, theme and QR code."
        actions={
          <LinkButton to="/dashboard/groups/new" leftIcon={<Plus className="h-4 w-4" />}>
            New group
          </LinkButton>
        }
      />

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Tabs
          tabs={FILTERS}
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          variant="pill"
          aria-label="Filter groups"
        />
        <Input
          type="search"
          placeholder="Search groups…"
          aria-label="Search groups"
          leftIcon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          containerClassName="w-full sm:w-72"
        />
      </div>

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : (data?.data.length ?? 0) === 0 ? (
        <EmptyState
          icon={<Globe className="h-6 w-6" aria-hidden="true" />}
          title={debouncedSearch ? 'No groups match your search' : 'Create your first group'}
          description={
            debouncedSearch
              ? 'Try a different name, or clear the search to see everything.'
              : 'A group gives your chapter a public page at /g/your-name and a QR code that keeps working even when the links behind it change.'
          }
          action={
            debouncedSearch ? (
              <Button variant="outline" onClick={() => setSearch('')}>
                Clear search
              </Button>
            ) : (
              <LinkButton to="/dashboard/groups/new" leftIcon={<Plus className="h-4 w-4" />}>
                Create a group
              </LinkButton>
            )
          }
        />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data?.data.map((group) => (
              <GroupCard
                key={group.id}
                group={group}
                onArchive={(item) =>
                  void run(() => groupsApi.archive(item.id), `“${item.name}” archived`)
                }
                onRestore={(item) =>
                  void run(() => groupsApi.restore(item.id), `“${item.name}” restored`)
                }
                onDelete={setConfirmDelete}
                onDuplicate={(item) =>
                  void run(async () => {
                    const copy = await groupsApi.duplicate(item.id);
                    navigate(`/dashboard/groups/${copy.id}`);
                  }, 'Group duplicated')
                }
              />
            ))}
          </div>

          {data && data.meta.pages > 1 && (
            <nav
              className="mt-6 flex items-center justify-between gap-4"
              aria-label="Pagination"
            >
              <p className="text-sm text-navy-500">
                Page {data.meta.page} of {data.meta.pages} · {data.meta.total} groups
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!data.meta.has_previous}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!data.meta.has_next}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </Button>
              </div>
            </nav>
          )}
        </>
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        isPending={isPending}
        title="Delete this group?"
        confirmLabel="Delete permanently"
        message={
          <>
            <strong className="text-navy-900">{confirmDelete?.name}</strong> and all of its
            links, QR design and analytics will be permanently removed. Anyone who scans a
            printed QR code for this group will get a “page not found”.
            <span className="mt-2 block">
              Archiving keeps the data and simply takes the page offline.
            </span>
          </>
        }
        onConfirm={async () => {
          if (!confirmDelete) return;
          await run(() => groupsApi.remove(confirmDelete.id), 'Group deleted');
          setConfirmDelete(null);
        }}
      />
    </>
  );
}

export default GroupsPage;
