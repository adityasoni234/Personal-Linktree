import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Eye, EyeOff, Lock, Mail, User } from 'lucide-react';

import { ApiError } from '@/api/client';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { Button, Callout, Checkbox, Input } from '@/components/ui';
import { useDocumentTitle } from '@/hooks';
import { cn } from '@/lib/utils';
import { passwordStrength, registerFormSchema, type RegisterFormValues } from '@/schemas';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/stores/toast';

const STRENGTH_STYLES = [
  'bg-danger-500',
  'bg-danger-500',
  'bg-warning-500',
  'bg-success-500',
  'bg-success-600',
];

function PasswordMeter({ password }: { password: string }) {
  const { score, label } = passwordStrength(password);

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2, 3].map((index) => (
          <span
            key={index}
            className={cn(
              'h-1 flex-1 rounded-full transition-colors',
              index < score ? STRENGTH_STYLES[score] : 'bg-navy-200',
            )}
          />
        ))}
      </div>
      {/* The strength is announced, not only shown as colour. */}
      <p className="text-2xs text-navy-500" aria-live="polite">
        Password strength: <span className="font-medium text-navy-700">{label}</span>
      </p>
    </div>
  );
}

export function RegisterPage() {
  useDocumentTitle('Create an account');
  const navigate = useNavigate();
  const signUp = useAuthStore((state) => state.signUp);

  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerFormSchema),
    mode: 'onBlur',
  });

  const password = watch('password') ?? '';

  const onSubmit = async (values: RegisterFormValues) => {
    setFormError(null);
    try {
      const user = await signUp({
        email: values.email,
        full_name: values.full_name,
        password: values.password,
      });
      toast.success('Account created', `Welcome to IEEE SOU Link Hub, ${user.full_name}.`);
      navigate('/dashboard', { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        // Surface server-side field errors on the matching input.
        const fieldErrors = error.fieldErrors;
        if (fieldErrors.length > 0) {
          for (const item of fieldErrors) {
            if (item.field in values) {
              setError(item.field as keyof RegisterFormValues, { message: item.message });
            }
          }
          if (!fieldErrors.some((item) => item.field in values)) setFormError(error.message);
        } else {
          setFormError(error.message);
        }
      } else {
        setFormError('Could not create your account. Please try again.');
      }
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Join your organization's link hub."
      footer={
        <p>
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-ieee-600 hover:underline">
            Sign in
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError && <Callout tone="danger">{formError}</Callout>}

        <Input
          label="Full name"
          autoComplete="name"
          autoFocus
          placeholder="Aarav Shah"
          leftIcon={<User className="h-4 w-4" />}
          error={errors.full_name?.message}
          {...register('full_name')}
        />

        <Input
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@ieeesou.org"
          leftIcon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register('email')}
        />

        <div className="space-y-2">
          <Input
            label="Password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            placeholder="At least 10 characters"
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
          {password && <PasswordMeter password={password} />}
        </div>

        <Input
          label="Confirm password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          leftIcon={<Lock className="h-4 w-4" />}
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />

        <Checkbox
          label="I will use this platform in line with IEEE SOU's acceptable use policy"
          {...register('accept_terms')}
        />
        {errors.accept_terms && (
          <p className="text-sm text-danger-600" role="alert">
            {errors.accept_terms.message}
          </p>
        )}

        <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}

export default RegisterPage;
