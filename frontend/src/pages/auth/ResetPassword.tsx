import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Lock, ShieldAlert } from 'lucide-react';

import { ApiError } from '@/api/client';
import { authApi } from '@/api/endpoints';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { Button, Callout, Input } from '@/components/ui';
import { useDocumentTitle } from '@/hooks';
import { resetPasswordSchema, type ResetPasswordValues } from '@/schemas';
import { toast } from '@/stores/toast';

export function ResetPasswordPage() {
  useDocumentTitle('Choose a new password');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({ resolver: zodResolver(resetPasswordSchema) });

  const onSubmit = async (values: ResetPasswordValues) => {
    setFormError(null);
    try {
      await authApi.resetPassword(token, values.new_password);
      toast.success('Password updated', 'Sign in with your new password.');
      navigate('/login', { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        const problems = (error.details as { problems?: string[] } | undefined)?.problems;
        if (problems?.length) {
          setError('new_password', { message: `Password ${problems.join('; ')}` });
        } else {
          setFormError(error.message);
        }
      } else {
        setFormError('Could not reset your password. Please request a new link.');
      }
    }
  };

  if (!token) {
    return (
      <AuthLayout title="This link is not valid">
        <div className="space-y-5">
          <div className="flex items-start gap-3 rounded-xl border border-warning-100 bg-warning-50/70 p-4">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-warning-600" aria-hidden="true" />
            <p className="text-sm text-navy-700">
              The reset link is missing or incomplete. Reset links expire after 30 minutes
              and can only be used once.
            </p>
          </div>
          <Link to="/forgot-password">
            <Button fullWidth>Request a new link</Button>
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Choose a new password"
      subtitle="For your security, this signs you out of every other device."
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError && <Callout tone="danger">{formError}</Callout>}

        <Input
          label="New password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          autoFocus
          placeholder="At least 10 characters"
          leftIcon={<Lock className="h-4 w-4" />}
          error={errors.new_password?.message}
          rightSlot={
            <button
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="rounded-lg p-2 text-navy-400 transition hover:bg-navy-100 hover:text-navy-700"
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Eye className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          }
          {...register('new_password')}
        />

        <Input
          label="Confirm new password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          leftIcon={<Lock className="h-4 w-4" />}
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />

        <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
          Update password
        </Button>
      </form>
    </AuthLayout>
  );
}

export default ResetPasswordPage;
