import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Search, ShieldAlert, UserPlus, UserX, Users as UsersIcon } from 'lucide-react';

import { ApiError } from '@/api/client';
import { adminApi } from '@/api/endpoints';
import type { AdminUserRow, Role } from '@/api/types';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Badge,
  Button,
  Card,
  Callout,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  Menu,
  Modal,
  RoleBadge,
  Select,
  SkeletonTable,
} from '@/components/ui';
import { useDebounced, useDocumentTitle, useQuery } from '@/hooks';
import { ROLE_DESCRIPTIONS, ROLE_LABELS, formatRelativeTime, initials } from '@/lib/utils';
import { memberInviteSchema, type MemberInviteValues } from '@/schemas';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/stores/toast';

const ASSIGNABLE: Role[] = ['USER', 'EDITOR', 'ADMIN'];

export function AdminUsersPage() {
  useDocumentTitle('Members');
  const currentUser = useAuthStore((state) => state.user);
  const isSuperAdmin = currentUser?.effective_role === 'SUPER_ADMIN';

  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [roleTarget, setRoleTarget] = useState<AdminUserRow | null>(null);
  const [nextRole, setNextRole] = useState<Role>('USER');
  const [suspendTarget, setSuspendTarget] = useState<AdminUserRow | null>(null);
  const [isPending, setIsPending] = useState(false);

  const { data, error, isLoading, refetch } = useQuery(
    () => adminApi.users({ page, limit: 20, search: debouncedSearch }),
    [page, debouncedSearch],
  );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<MemberInviteValues>({
    resolver: zodResolver(memberInviteSchema),
    defaultValues: { role: 'USER' },
  });

  const invite = async (values: MemberInviteValues) => {
    try {
      await adminApi.addMember(values.email, values.role);
      toast.success('Member added', `${values.email} can now sign in to this organization.`);
      setInviteOpen(false);
      reset({ role: 'USER' });
      await refetch();
    } catch (caught) {
      toast.error(
        'Could not add the member',
        caught instanceof ApiError ? caught.message : undefined,
      );
    }
  };

  const changeRole = async () => {
    if (!roleTarget) return;
    setIsPending(true);
    try {
      await adminApi.changeRole(roleTarget.id, nextRole);
      toast.success('Role updated', `${roleTarget.full_name} is now ${ROLE_LABELS[nextRole]}.`);
      setRoleTarget(null);
      await refetch();
    } catch (caught) {
      toast.error(
        'Could not change the role',
        caught instanceof ApiError ? caught.message : undefined,
      );
    } finally {
      setIsPending(false);
    }
  };

  const toggleSuspension = async () => {
    if (!suspendTarget) return;
    const next = suspendTarget.status === 'SUSPENDED' ? 'ACTIVE' : 'SUSPENDED';
    setIsPending(true);
    try {
      await adminApi.changeStatus(suspendTarget.id, next);
      toast.success(next === 'SUSPENDED' ? 'Account suspended' : 'Account reactivated');
      setSuspendTarget(null);
      await refetch();
    } catch (caught) {
      toast.error(
        'Could not update the account',
        caught instanceof ApiError ? caught.message : undefined,
      );
    } finally {
      setIsPending(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Members"
        description="Who can sign in, and what each of them is allowed to do."
        actions={
          <Button leftIcon={<UserPlus className="h-4 w-4" />} onClick={() => setInviteOpen(true)}>
            Add member
          </Button>
        }
      />

      <div className="mb-5">
        <Input
          type="search"
          placeholder="Search by name or email…"
          aria-label="Search members"
          leftIcon={<Search className="h-4 w-4" />}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          containerClassName="w-full sm:w-80"
        />
      </div>

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : isLoading ? (
        <Card>
          <div className="p-5">
            <SkeletonTable rows={6} />
          </div>
        </Card>
      ) : (data?.data.length ?? 0) === 0 ? (
        <EmptyState
          icon={<UsersIcon className="h-6 w-6" aria-hidden="true" />}
          title="No members found"
          description="Try a different search, or add someone who has already registered."
        />
      ) : (
        <Card>
          <div className="scroll-x">
            <table className="w-full min-w-[48rem] text-sm">
              <caption className="sr-only">Organization members</caption>
              <thead>
                <tr className="border-b border-navy-200/70 text-left text-xs text-navy-500">
                  <th scope="col" className="px-5 py-3 font-medium">Member</th>
                  <th scope="col" className="px-3 py-3 font-medium">Role</th>
                  <th scope="col" className="px-3 py-3 text-right font-medium">Groups</th>
                  <th scope="col" className="px-3 py-3 font-medium">Status</th>
                  <th scope="col" className="px-3 py-3 font-medium">Last sign-in</th>
                  <th scope="col" className="px-5 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data?.data.map((member) => {
                  const isSelf = member.id === currentUser?.id;
                  const effectiveRole =
                    member.system_role === 'SUPER_ADMIN'
                      ? 'SUPER_ADMIN'
                      : (member.organization_role ?? 'USER');

                  return (
                    <tr
                      key={member.id}
                      className="border-b border-navy-100 transition last:border-0 hover:bg-surface-subtle"
                    >
                      <th scope="row" className="px-5 py-3 text-left font-normal">
                        <span className="flex items-center gap-3">
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-navy-900 text-2xs font-semibold text-white">
                            {initials(member.full_name)}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate font-medium text-navy-900">
                              {member.full_name}
                              {isSelf && (
                                <span className="ml-1.5 text-2xs font-normal text-navy-400">
                                  (you)
                                </span>
                              )}
                            </span>
                            <span className="block truncate text-2xs text-navy-400">
                              {member.email}
                            </span>
                          </span>
                        </span>
                      </th>
                      <td className="px-3 py-3">
                        <RoleBadge role={effectiveRole} />
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-navy-700">
                        {member.group_count}
                      </td>
                      <td className="px-3 py-3">
                        <Badge
                          tone={
                            member.status === 'ACTIVE'
                              ? 'success'
                              : member.status === 'SUSPENDED'
                                ? 'danger'
                                : 'neutral'
                          }
                          dot
                          size="sm"
                        >
                          {member.status.charAt(0) + member.status.slice(1).toLowerCase()}
                        </Badge>
                      </td>
                      <td className="px-3 py-3 text-navy-500">
                        {member.last_login_at
                          ? formatRelativeTime(member.last_login_at)
                          : 'Never'}
                      </td>
                      <td className="px-5 py-3 text-right">
                        {!isSelf && (
                          <Menu
                            label={`Actions for ${member.full_name}`}
                            items={[
                              {
                                label: 'Change role',
                                icon: <ShieldAlert className="h-4 w-4" />,
                                onSelect: () => {
                                  setRoleTarget(member);
                                  setNextRole(effectiveRole as Role);
                                },
                              },
                              {
                                label:
                                  member.status === 'SUSPENDED'
                                    ? 'Reactivate account'
                                    : 'Suspend account',
                                icon: <UserX className="h-4 w-4" />,
                                tone: member.status === 'SUSPENDED' ? 'default' : 'danger',
                                separated: true,
                                onSelect: () => setSuspendTarget(member),
                              },
                            ]}
                          />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {data && data.meta.pages > 1 && (
            <nav
              className="flex items-center justify-between gap-4 border-t border-navy-200/70 px-5 py-3"
              aria-label="Pagination"
            >
              <p className="text-sm text-navy-500">
                {data.meta.total} members · page {data.meta.page} of {data.meta.pages}
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

      {/* ---- Add member ---- */}
      <Modal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        title="Add a member"
        description="The person must already have an account. Adding them grants access to this organization."
        footer={
          <>
            <Button variant="ghost" onClick={() => setInviteOpen(false)}>
              Cancel
            </Button>
            <Button isLoading={isSubmitting} onClick={handleSubmit(invite)}>
              Add member
            </Button>
          </>
        }
      >
        <form onSubmit={handleSubmit(invite)} className="space-y-4" noValidate>
          <Input
            label="Email"
            type="email"
            autoFocus
            placeholder="member@ieeesou.org"
            error={errors.email?.message}
            {...register('email')}
          />
          <Select
            label="Role"
            options={ASSIGNABLE.map((role) => ({
              value: role,
              label: ROLE_LABELS[role] ?? role,
            }))}
            error={errors.role?.message}
            {...register('role')}
          />
          <Callout tone="info">
            You can never grant a role higher than your own, and role changes take effect
            immediately — the member's existing sessions are re-evaluated on their next request.
          </Callout>
        </form>
      </Modal>

      {/* ---- Change role ---- */}
      <Modal
        open={roleTarget !== null}
        onClose={() => setRoleTarget(null)}
        title={`Change role for ${roleTarget?.full_name ?? ''}`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRoleTarget(null)} disabled={isPending}>
              Cancel
            </Button>
            <Button isLoading={isPending} onClick={() => void changeRole()}>
              Update role
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {(isSuperAdmin ? [...ASSIGNABLE, 'SUPER_ADMIN' as Role] : ASSIGNABLE).map((role) => (
            <label
              key={role}
              className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition ${
                nextRole === role
                  ? 'border-ieee-600 bg-ieee-50/50 ring-2 ring-ieee-600/20'
                  : 'border-navy-200 hover:border-navy-300'
              }`}
            >
              <input
                type="radio"
                name="role"
                value={role}
                checked={nextRole === role}
                onChange={() => setNextRole(role)}
                className="mt-1 h-4 w-4 accent-ieee-600"
              />
              <span>
                <span className="block text-sm font-medium text-navy-900">
                  {ROLE_LABELS[role]}
                </span>
                <span className="block text-sm text-navy-500 text-pretty">
                  {ROLE_DESCRIPTIONS[role]}
                </span>
              </span>
            </label>
          ))}
        </div>
      </Modal>

      {/* ---- Suspend ---- */}
      <ConfirmDialog
        open={suspendTarget !== null}
        onClose={() => setSuspendTarget(null)}
        isPending={isPending}
        tone={suspendTarget?.status === 'SUSPENDED' ? 'primary' : 'danger'}
        title={
          suspendTarget?.status === 'SUSPENDED' ? 'Reactivate account?' : 'Suspend account?'
        }
        confirmLabel={
          suspendTarget?.status === 'SUSPENDED' ? 'Reactivate' : 'Suspend account'
        }
        message={
          suspendTarget?.status === 'SUSPENDED' ? (
            <>
              <strong className="text-navy-900">{suspendTarget?.full_name}</strong> will be
              able to sign in again. Their groups and links are untouched.
            </>
          ) : (
            <>
              <strong className="text-navy-900">{suspendTarget?.full_name}</strong> will be
              signed out everywhere and blocked from signing in. Their groups stay published —
              suspending a person does not take their pages offline.
            </>
          )
        }
        onConfirm={() => void toggleSuspension()}
      />
    </>
  );
}

export default AdminUsersPage;
