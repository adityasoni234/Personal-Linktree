import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Lock, Mail } from 'lucide-react';

import { ApiError } from '@/api/client';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { Button, Callout, Checkbox, Input } from '@/components/ui';
import { useDocumentTitle } from '@/hooks';
import { loginFormSchema, type LoginFormValues } from '@/schemas';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/stores/toast';

export function LoginPage() {
  useDocumentTitle('Sign in');
  const navigate = useNavigate();
  const location = useLocation();
  const signIn = useAuthStore((state) => state.signIn);

  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: { email: '', password: '', remember_me: false },
  });

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null);
    setRetryAfter(null);
    try {
      const user = await signIn(values.email, values.password, values.remember_me);
      toast.success(`Welcome back, ${user.full_name.split(' ')[0]}`);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? '/dashboard', { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        // The server intentionally does not say whether the account exists, and
        // neither does this message.
        setFormError(error.message);
        if (error.isRateLimited) setRetryAfter(error.retryAfterSeconds);
      } else {
        setFormError('Sign in failed. Please try again.');
      }
    }
  };

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Manage your chapter's links, pages and QR codes."
      footer={
        <p>
          New to Link Hub?{' '}
          <Link to="/register" className="font-semibold text-ieee-600 hover:underline">
            Create an account
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError && (
          <Callout tone={retryAfter ? 'warning' : 'danger'}>
            {formError}
            {retryAfter ? ` Try again in about ${Math.ceil(retryAfter / 60)} minute(s).` : ''}
          </Callout>
        )}

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

        <Input
          label="Password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="current-password"
          placeholder="••••••••••"
          leftIcon={<Lock className="h-4 w-4" />}
          error={errors.password?.message}
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
          {...register('password')}
        />

        <div className="flex items-center justify-between gap-4">
          <Checkbox label="Keep me signed in" {...register('remember_me')} />
          <Link
            to="/forgot-password"
            className="text-sm font-medium text-ieee-600 hover:underline"
          >
            Forgot password?
          </Link>
        </div>

        <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}

export default LoginPage;
