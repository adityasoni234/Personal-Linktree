import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Mail, ShieldCheck, User } from 'lucide-react';

import { authApi } from '@/api/endpoints';
import { PageHeader } from '@/components/layout/DashboardLayout';
import { Button, Card, CardBody, CardHeader, Input, RoleBadge } from '@/components/ui';
import { useDocumentTitle } from '@/hooks';
import { ROLE_DESCRIPTIONS, formatDate, initials } from '@/lib/utils';
import { profileFormSchema, type ProfileFormValues } from '@/schemas';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/stores/toast';

export function ProfilePage() {
  useDocumentTitle('Profile');
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    values: { full_name: user?.full_name ?? '' },
  });

  const onSubmit = async (values: ProfileFormValues) => {
    try {
      const updated = await authApi.updateProfile({ full_name: values.full_name });
      setUser(updated);
      toast.success('Profile updated');
    } catch (error) {
      toast.error('Could not save', error instanceof Error ? error.message : undefined);
    }
  };

  if (!user) return null;

  return (
    <>
      <PageHeader title="Profile" description="Your account details and role." />

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card>
          <CardHeader
            title="Personal details"
            icon={<User className="h-4 w-4" aria-hidden="true" />}
          />
          <CardBody>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
              <Input
                label="Full name"
                error={errors.full_name?.message}
                {...register('full_name')}
              />

              <Input
                label="Email"
                value={user.email}
                readOnly
                disabled
                leftIcon={<Mail className="h-4 w-4" />}
                hint="Contact an administrator to change the email on your account."
              />

              <div className="flex justify-end">
                <Button type="submit" isLoading={isSubmitting} disabled={!isDirty}>
                  Save changes
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardBody className="text-center">
              <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-navy-900 text-lg font-semibold text-white">
                {initials(user.full_name)}
              </span>
              <p className="mt-3 font-semibold text-navy-900">{user.full_name}</p>
              <p className="text-sm text-navy-500">{user.email}</p>
              <div className="mt-3 flex justify-center">
                <RoleBadge role={user.effective_role} />
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Your access"
              icon={<ShieldCheck className="h-4 w-4" aria-hidden="true" />}
            />
            <CardBody className="space-y-3 text-sm">
              <p className="text-navy-600 text-pretty">
                {ROLE_DESCRIPTIONS[user.effective_role]}
              </p>
              <dl className="space-y-2 border-t border-navy-100 pt-3 text-navy-600">
                <div className="flex justify-between gap-3">
                  <dt>Organization</dt>
                  <dd className="font-medium text-navy-900">
                    {user.organization_name ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>Member since</dt>
                  <dd className="font-medium text-navy-900">{formatDate(user.created_at)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>Last sign-in</dt>
                  <dd className="font-medium text-navy-900">
                    {user.last_login_at ? formatDate(user.last_login_at, 'long') : '—'}
                  </dd>
                </div>
              </dl>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}

export default ProfilePage;
