import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, Mail, MailCheck } from 'lucide-react';

import { ApiError } from '@/api/client';
import { authApi } from '@/api/endpoints';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { Button, Callout, Input } from '@/components/ui';
import { useDocumentTitle } from '@/hooks';
import { forgotPasswordSchema, type ForgotPasswordValues } from '@/schemas';

export function ForgotPasswordPage() {
  useDocumentTitle('Reset your password');
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: '' },
  });

  const onSubmit = async (values: ForgotPasswordValues) => {
    setFormError(null);
    try {
      await authApi.forgotPassword(values.email);
      // The server responds identically whether or not the account exists, and
      // so does this screen.
      setSent(true);
    } catch (error) {
      setFormError(
        error instanceof ApiError
          ? error.message
          : 'Could not send the reset email. Please try again.',
      );
    }
  };

  if (sent) {
    return (
      <AuthLayout
        title="Check your inbox"
        subtitle="If an account exists for that address, we have sent reset instructions."
      >
        <div className="space-y-5">
          <div className="flex items-start gap-3 rounded-xl border border-success-100 bg-success-50/70 p-4">
            <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-success-600" aria-hidden="true" />
            <div className="min-w-0 text-sm text-navy-700">
              <p className="font-medium text-navy-900">
                Sent to {getValues('email')}
              </p>
              <p className="mt-1">
                The link expires in 30 minutes and can be used once. Check your spam folder
                if it does not arrive within a few minutes.
              </p>
            </div>
          </div>

          <Button variant="outline" fullWidth onClick={() => setSent(false)}>
            Use a different email
          </Button>

          <Link
            to="/login"
            className="flex items-center justify-center gap-1.5 text-sm font-medium text-ieee-600 hover:underline"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter the email on your account and we will send a reset link."
      footer={
        <Link
          to="/login"
          className="flex items-center gap-1.5 font-semibold text-ieee-600 hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError && <Callout tone="danger">{formError}</Callout>}

        <Input
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
          placeholder="you@ieeesou.org"
          leftIcon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register('email')}
        />

        <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
          Send reset link
        </Button>
      </form>
    </AuthLayout>
  );
}

export default ForgotPasswordPage;
