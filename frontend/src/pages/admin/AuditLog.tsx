import { useState } from 'react';
import { ClipboardList, ShieldCheck } from 'lucide-react';

import { adminApi } from '@/api/endpoints';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Select,
  SkeletonTable,
} from '@/components/ui';
import { useDocumentTitle, useQuery } from '@/hooks';
import { formatDate, formatRelativeTime } from '@/lib/utils';

const ACTION_GROUPS = [
  { value: '', label: 'All actions' },
  { value: 'LOGIN_SUCCEEDED', label: 'Sign-ins' },
  { value: 'LOGIN_FAILED', label: 'Failed sign-ins' },
  { value: 'PASSWORD_CHANGED', label: 'Password changes' },
  { value: 'GROUP_CREATED', label: 'Groups created' },
  { value: 'GROUP_DELETED', label: 'Groups deleted' },
  { value: 'LINK_CREATED', label: 'Links added' },
  { value: 'LINK_DELETED', label: 'Links removed' },
  { value: 'QR_CONFIG_UPDATED', label: 'QR design changes' },
  { value: 'ROLE_CHANGED', label: 'Role changes' },
  { value: 'USER_SUSPENDED', label: 'Suspensions' },
  { value: 'TOKEN_REUSE_DETECTED', label: 'Token reuse alerts' },
];

/** Actions that should stand out when scanning the list. */
const SECURITY_ACTIONS = new Set([
  'LOGIN_FAILED',
  'TOKEN_REUSE_DETECTED',
  'ROLE_CHANGED',
  'USER_SUSPENDED',
  'USER_DELETED',
  'PASSWORD_RESET_COMPLETED',
]);

function humanise(action: string): string {
  return action
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/^\w/, (character) => character.toUpperCase());
}

export function AuditLogPage() {
  useDocumentTitle('Audit log');
  const [action, setAction] = useState('');
  const [page, setPage] = useState(1);

  const { data, error, isLoading, refetch } = useQuery(
    () => adminApi.auditLogs({ page, limit: 25, action: action || undefined }),
    [page, action],
  );

  return (
    <>
      <PageHeader
        title="Audit log"
        description="An append-only record of security-sensitive actions. Passwords, tokens and secrets are never written here."
        actions={
          <Select
            aria-label="Filter by action"
            options={ACTION_GROUPS}
            value={action}
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
            className="w-56"
          />
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : isLoading ? (
        <Card>
          <div className="p-5">
            <SkeletonTable rows={8} />
          </div>
        </Card>
      ) : (data?.data.length ?? 0) === 0 ? (
        <EmptyState
          icon={<ClipboardList className="h-6 w-6" aria-hidden="true" />}
          title="Nothing recorded yet"
          description="Entries appear here as soon as members start creating groups, editing links or signing in."
        />
      ) : (
        <Card>
          <div className="scroll-x">
            <table className="w-full min-w-[44rem] text-sm">
              <caption className="sr-only">Audit log entries</caption>
              <thead>
                <tr className="border-b border-navy-200/70 text-left text-xs text-navy-500">
                  <th scope="col" className="px-5 py-3 font-medium">Action</th>
                  <th scope="col" className="px-3 py-3 font-medium">Actor</th>
                  <th scope="col" className="px-3 py-3 font-medium">Resource</th>
                  <th scope="col" className="px-3 py-3 font-medium">Details</th>
                  <th scope="col" className="px-5 py-3 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {data?.data.map((entry) => (
                  <tr
                    key={entry.id}
                    className="border-b border-navy-100 align-top transition last:border-0 hover:bg-surface-subtle"
                  >
                    <th scope="row" className="px-5 py-3 text-left font-normal">
                      <Badge
                        tone={SECURITY_ACTIONS.has(entry.action) ? 'warning' : 'neutral'}
                        size="sm"
                      >
                        {humanise(entry.action)}
                      </Badge>
                    </th>
                    <td className="px-3 py-3 text-navy-700">
                      {entry.actor_email ?? <span className="text-navy-400">system</span>}
                    </td>
                    <td className="px-3 py-3 text-navy-600">
                      {entry.resource_type ? (
                        <span className="font-mono text-2xs">
                          {entry.resource_type.toLowerCase()}
                          {entry.resource_id && (
                            <span className="text-navy-400">
                              {' '}
                              {entry.resource_id.slice(0, 8)}
                            </span>
                          )}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="max-w-xs px-3 py-3">
                      {Object.keys(entry.event_metadata ?? {}).length === 0 ? (
                        <span className="text-navy-400">—</span>
                      ) : (
                        <dl className="space-y-0.5">
                          {Object.entries(entry.event_metadata)
                            .slice(0, 3)
                            .map(([key, value]) => (
                              <div key={key} className="flex gap-1.5 text-2xs">
                                <dt className="text-navy-400">{key}:</dt>
                                <dd className="truncate text-navy-700">{String(value)}</dd>
                              </div>
                            ))}
                        </dl>
                      )}
                    </td>
                    <td className="px-5 py-3 text-navy-500">
                      <span title={formatDate(entry.created_at, 'long')}>
                        {formatRelativeTime(entry.created_at)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data && data.meta.pages > 1 && (
            <nav
              className="flex items-center justify-between gap-4 border-t border-navy-200/70 px-5 py-3"
              aria-label="Pagination"
            >
              <p className="text-sm text-navy-500">
                {data.meta.total} entries · page {data.meta.page} of {data.meta.pages}
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
        </Card>
      )}

      <p className="mt-4 flex items-center gap-2 px-1 text-2xs text-navy-500">
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
        IP addresses are stored as salted hashes, never in raw form.
      </p>
    </>
  );
}

export default AuditLogPage;
