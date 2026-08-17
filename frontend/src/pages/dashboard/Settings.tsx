import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Building2, KeyRound, Laptop, LogOut, Trash2 } from 'lucide-react';

import { ApiError } from '@/api/client';
import { adminApi, authApi } from '@/api/endpoints';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Badge,
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  ConfirmDialog,
  Input,
  Skeleton,
} from '@/components/ui';
import { useDocumentTitle, useQuery } from '@/hooks';
import { formatRelativeTime } from '@/lib/utils';
import { changePasswordSchema, type ChangePasswordValues } from '@/schemas';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/stores/toast';

export function SettingsPage() {
  useDocumentTitle('Settings');
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);

  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmSignOutAll, setConfirmSignOutAll] = useState(false);

  const sessionsQuery = useQuery(() => authApi.sessions(), []);
  const orgQuery = useQuery(() => adminApi.organization(), [], {
    enabled: Boolean(user && ['ADMIN', 'SUPER_ADMIN'].includes(user.effective_role)),
  });

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { revoke_other_sessions: true },
  });

  const onChangePassword = async (values: ChangePasswordValues) => {
    setPasswordError(null);
    try {
      await authApi.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
        revoke_other_sessions: values.revoke_other_sessions,
      });
      reset({ revoke_other_sessions: true });
      toast.success('Password changed', 'Other devices have been signed out.');
      await sessionsQuery.refetch();
    } catch (error) {
      if (error instanceof ApiError) {
        const field = (error.details as { field?: string } | undefined)?.field;
        if (field === 'current_password') {
          setError('current_password', { message: error.message });
        } else if (field === 'password' || field === 'new_password') {
          setError('new_password', { message: error.message });
        } else {
          setPasswordError(error.message);
        }
      } else {
        setPasswordError('Could not change your password.');
      }
    }
  };

  return (
    <>
      <PageHeader
        title="Settings"
        description="Security, sessions and organization preferences."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ---- Password ---- */}
        <Card>
          <CardHeader
            title="Change password"
            description="Passwords are stored with Argon2id and never in plain text."
            icon={<KeyRound className="h-4 w-4" aria-hidden="true" />}
          />
          <CardBody>
            <form onSubmit={handleSubmit(onChangePassword)} className="space-y-4" noValidate>
              {passwordError && <Callout tone="danger">{passwordError}</Callout>}

              <Input
                label="Current password"
                type="password"
                autoComplete="current-password"
                error={errors.current_password?.message}
                {...register('current_password')}
              />
              <Input
                label="New password"
                type="password"
                autoComplete="new-password"
                hint="At least 10 characters, mixing three character types."
                error={errors.new_password?.message}
                {...register('new_password')}
              />
              <Input
                label="Confirm new password"
                type="password"
                autoComplete="new-password"
                error={errors.confirm_password?.message}
                {...register('confirm_password')}
              />

              <Checkbox
                label="Sign out of all other devices"
                description="Recommended — this ends any session you did not start."
                {...register('revoke_other_sessions')}
              />

              <div className="flex justify-end">
                <Button type="submit" isLoading={isSubmitting}>
                  Change password
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>

        {/* ---- Sessions ---- */}
        <Card>
          <CardHeader
            title="Active sessions"
            description="Devices currently signed in to your account"
            icon={<Laptop className="h-4 w-4" aria-hidden="true" />}
            action={
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<LogOut className="h-4 w-4" />}
                onClick={() => setConfirmSignOutAll(true)}
              >
                Sign out everywhere
              </Button>
            }
          />
          <CardBody>
            {sessionsQuery.isLoading ? (
              <div className="space-y-3">
                {[0, 1].map((index) => (
                  <Skeleton key={index} className="h-14 w-full" />
                ))}
              </div>
            ) : (sessionsQuery.data?.length ?? 0) === 0 ? (
              <p className="py-6 text-center text-sm text-navy-500">No active sessions.</p>
            ) : (
              <ul className="space-y-2">
                {sessionsQuery.data?.map((session) => (
                  <li
                    key={session.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-navy-200/70 p-3"
                  >
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 truncate text-sm font-medium text-navy-900">
                        {session.user_agent_label?.slice(0, 48) ?? 'Unknown device'}
                        {session.is_current && (
                          <Badge tone="success" size="sm">
                            This device
                          </Badge>
                        )}
                      </p>
                      <p className="text-2xs text-navy-400">
                        Last used{' '}
                        {session.last_used_at
                          ? formatRelativeTime(session.last_used_at)
                          : formatRelativeTime(session.created_at)}
                      </p>
                    </div>
                    {!session.is_current && (
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={<Trash2 className="h-4 w-4" />}
                        onClick={() => {
                          void authApi
                            .revokeSession(session.id)
                            .then(() => {
                              toast.success('Session revoked');
                              return sessionsQuery.refetch();
                            })
                            .catch(() => toast.error('Could not revoke that session'));
                        }}
                      >
                        Revoke
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        {/* ---- Organization ---- */}
        {orgQuery.data && (
          <Card className="lg:col-span-2">
            <CardHeader
              title="Organization"
              description="Visible to administrators only"
              icon={<Building2 className="h-4 w-4" aria-hidden="true" />}
            />
            <CardBody>
              <dl className="grid gap-4 sm:grid-cols-4">
                {[
                  { label: 'Name', value: orgQuery.data.name },
                  { label: 'Address', value: `/${orgQuery.data.slug}` },
                  { label: 'Members', value: String(orgQuery.data.member_count) },
                  { label: 'Groups', value: String(orgQuery.data.group_count) },
                ].map((item) => (
                  <div key={item.label}>
                    <dt className="text-2xs uppercase tracking-wide text-navy-400">
                      {item.label}
                    </dt>
                    <dd className="mt-0.5 font-medium text-navy-900">{item.value}</dd>
                  </div>
                ))}
              </dl>

              <div className="mt-5 border-t border-navy-100 pt-4">
                <h3 className="text-sm font-semibold text-navy-900">Membership</h3>
                <p className="mt-1 text-sm text-navy-600 text-pretty">
                  {orgQuery.data.settings.allow_public_registration
                    ? 'Anyone with an email address can register and join this organization as a member.'
                    : 'Registration is closed — an administrator must add new members.'}{' '}
                  New members join as{' '}
                  <strong>{orgQuery.data.settings.default_member_role.toLowerCase()}</strong>.
                </p>
              </div>
            </CardBody>
          </Card>
        )}
      </div>

      <ConfirmDialog
        open={confirmSignOutAll}
        onClose={() => setConfirmSignOutAll(false)}
        title="Sign out of every device?"
        confirmLabel="Sign out everywhere"
        tone="primary"
        message="Every session, including this one, will end. You will need to sign in again."
        onConfirm={async () => {
          await signOut({ everywhere: true });
          window.location.assign('/login');
        }}
      />
    </>
  );
}

export default SettingsPage;
