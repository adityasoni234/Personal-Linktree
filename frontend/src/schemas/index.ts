/**
 * Client-side validation schemas.
 *
 * These exist to give fast, field-level feedback — they are *not* a security
 * control. The backend re-validates everything with the equivalent Pydantic
 * models, and its answer is the one that counts.
 */

import { z } from 'zod';

const RESERVED_SLUGS = new Set([
  'admin', 'api', 'app', 'auth', 'dashboard', 'docs', 'g', 'group', 'groups',
  'health', 'help', 'login', 'logout', 'media', 'new', 'profile', 'public', 'qr',
  'register', 'reset-password', 'forgot-password', 'settings', 'signin', 'signup',
  'static', 'support', 'system', 'user', 'users', 'v1', 'www',
]);

export const emailSchema = z
  .string()
  .trim()
  .min(1, 'Email is required')
  .max(320, 'Email is too long')
  .email('Enter a valid email address')
  .transform((value) => value.toLowerCase());

/** Mirrors `validate_password_strength` on the server. */
export const passwordSchema = z
  .string()
  .min(10, 'Use at least 10 characters')
  .max(128, 'Use at most 128 characters')
  .refine((value) => value === value.trim(), 'Must not start or end with a space')
  .refine((value) => {
    const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((pattern) =>
      pattern.test(value),
    ).length;
    return classes >= 3;
  }, 'Mix at least three of: lowercase, uppercase, numbers, symbols')
  .refine(
    (value) => !/(.)\1{3,}/.test(value),
    'Avoid repeating the same character four or more times',
  );

export const slugSchema = z
  .string()
  .trim()
  .toLowerCase()
  .min(3, 'Use at least 3 characters')
  .max(48, 'Use at most 48 characters')
  .regex(
    /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
    'Use lowercase letters, numbers and single hyphens only',
  )
  .refine((value) => !RESERVED_SLUGS.has(value), 'That address is reserved')
  .refine((value) => !/^\d+$/.test(value), 'Must contain at least one letter');

/**
 * Accepts a bare domain and normalises it to https, matching the server.
 * Dangerous schemes are rejected outright rather than silently stripped.
 */
export const linkUrlSchema = z
  .string()
  .trim()
  .min(1, 'A URL is required')
  .max(2048, 'URL is too long')
  .refine(
    (value) => !/^\s*(javascript|data|vbscript|file|blob|about):/i.test(value),
    'That kind of link is not allowed',
  )
  .transform((value) =>
    /^[a-z][a-z0-9+.-]*:/i.test(value) ? value : `https://${value}`,
  )
  .refine((value) => {
    try {
      const url = new URL(value);
      if (url.protocol === 'mailto:' || url.protocol === 'tel:') return true;
      return (
        (url.protocol === 'https:' || url.protocol === 'http:') &&
        url.hostname.includes('.')
      );
    } catch {
      return false;
    }
  }, 'Enter a valid link, for example https://ieeesou.org');

export const hexColorSchema = z
  .string()
  .trim()
  .regex(/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/, 'Use a hex colour like #00629B');

/* -------------------------------------------------------------------------- */
/* Forms                                                                       */
/* -------------------------------------------------------------------------- */

export const loginFormSchema = z.object({
  email: emailSchema,
  // Deliberately lenient: an existing password must not be re-validated against
  // the current policy, or people whose password predates a policy change get
  // locked out of their own sign-in form.
  password: z.string().min(1, 'Password is required').max(128),
  remember_me: z.boolean().default(false),
});
export type LoginFormValues = z.infer<typeof loginFormSchema>;

export const registerFormSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .min(2, 'Enter your full name')
      .max(120, 'Name is too long'),
    email: emailSchema,
    password: passwordSchema,
    confirm_password: z.string(),
    accept_terms: z.literal(true, {
      errorMap: () => ({ message: 'Please accept the acceptable use policy' }),
    }),
  })
  .refine((values) => values.password === values.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })
  .refine(
    (values) =>
      !values.password.toLowerCase().includes(values.email.split('@')[0]?.toLowerCase() ?? '###'),
    { message: 'Password must not contain your email address', path: ['password'] },
  );
export type RegisterFormValues = z.infer<typeof registerFormSchema>;

export const forgotPasswordSchema = z.object({ email: emailSchema });
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    new_password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: passwordSchema,
    confirm_password: z.string(),
    revoke_other_sessions: z.boolean().default(true),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })
  .refine((values) => values.current_password !== values.new_password, {
    message: 'Choose a password different from your current one',
    path: ['new_password'],
  });
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;

export const groupFormSchema = z.object({
  name: z.string().trim().min(2, 'Give the group a name').max(120, 'Name is too long'),
  slug: slugSchema,
  description: z.string().trim().max(500, 'Keep the description under 500 characters').optional(),
  logo_url: z.string().trim().max(512).optional().or(z.literal('')),
});
export type GroupFormValues = z.infer<typeof groupFormSchema>;

export const linkFormSchema = z.object({
  title: z.string().trim().min(1, 'Give the link a title').max(120, 'Title is too long'),
  url: linkUrlSchema,
  description: z.string().trim().max(200, 'Keep it under 200 characters').optional(),
  icon: z.string().trim().max(64).optional(),
  is_active: z.boolean().default(true),
});
export type LinkFormValues = z.infer<typeof linkFormSchema>;

export const profileFormSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter your full name').max(120),
});
export type ProfileFormValues = z.infer<typeof profileFormSchema>;

export const memberInviteSchema = z.object({
  email: emailSchema,
  role: z.enum(['USER', 'EDITOR', 'ADMIN', 'SUPER_ADMIN']),
});
export type MemberInviteValues = z.infer<typeof memberInviteSchema>;

export const organizationFormSchema = z.object({
  name: z.string().trim().min(2, 'Enter the organization name').max(120),
  description: z.string().trim().max(500).optional(),
  website_url: z.string().trim().max(512).optional().or(z.literal('')),
});
export type OrganizationFormValues = z.infer<typeof organizationFormSchema>;

/** Rough strength meter for the registration form's live feedback. */
export function passwordStrength(password: string): {
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
} {
  if (!password) return { score: 0, label: 'Enter a password' };

  let score = 0;
  if (password.length >= 10) score += 1;
  if (password.length >= 14) score += 1;
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((pattern) =>
    pattern.test(password),
  ).length;
  if (classes >= 3) score += 1;
  if (classes === 4 && password.length >= 12) score += 1;
  if (/(.)\1{3,}/.test(password)) score = Math.max(0, score - 1);

  const labels = ['Too weak', 'Weak', 'Fair', 'Strong', 'Very strong'] as const;
  const clamped = Math.min(4, score) as 0 | 1 | 2 | 3 | 4;
  return { score: clamped, label: labels[clamped] };
}
