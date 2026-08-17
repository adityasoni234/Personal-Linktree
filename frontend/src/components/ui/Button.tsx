import { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

import { cn } from '@/lib/utils';

export type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'ghost'
  | 'danger'
  | 'outline'
  | 'subtle';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

const BASE =
  'inline-flex items-center justify-center gap-2 font-medium whitespace-nowrap ' +
  'rounded-xl transition-[background-color,border-color,color,box-shadow,transform] ' +
  'duration-150 select-none ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ' +
  'focus-visible:ring-ieee-600 focus-visible:ring-offset-white ' +
  'disabled:pointer-events-none disabled:opacity-50 active:translate-y-px';

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-ieee-600 text-white shadow-card hover:bg-ieee-700 active:bg-ieee-800',
  secondary:
    'bg-navy-900 text-white shadow-card hover:bg-navy-800 active:bg-navy-900',
  outline:
    'border border-navy-200 bg-white text-navy-800 shadow-card hover:border-navy-300 hover:bg-surface-subtle',
  subtle: 'bg-ieee-50 text-ieee-700 hover:bg-ieee-100',
  ghost: 'text-navy-600 hover:bg-navy-100 hover:text-navy-900',
  danger: 'bg-danger-600 text-white shadow-card hover:bg-danger-700 active:bg-danger-700',
};

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-9 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
  icon: 'h-10 w-10 p-0',
};

interface CommonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export interface ButtonProps
  extends CommonProps,
    React.ButtonHTMLAttributes<HTMLButtonElement> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    isLoading = false,
    fullWidth = false,
    leftIcon,
    rightIcon,
    className,
    children,
    disabled,
    type = 'button',
    ...props
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      // `aria-busy` tells assistive tech the control is working; the spinner
      // alone would be invisible to it.
      aria-busy={isLoading || undefined}
      disabled={disabled || isLoading}
      className={cn(BASE, VARIANTS[variant], SIZES[size], fullWidth && 'w-full', className)}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        leftIcon
      )}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
});

export interface LinkButtonProps
  extends CommonProps,
    Omit<React.ComponentProps<typeof Link>, 'className'> {
  className?: string;
}

/** Same visual language as `Button`, but renders a real anchor for navigation. */
export function LinkButton({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  leftIcon,
  rightIcon,
  className,
  children,
  ...props
}: LinkButtonProps) {
  return (
    <Link
      className={cn(BASE, VARIANTS[variant], SIZES[size], fullWidth && 'w-full', className)}
      {...props}
    >
      {leftIcon}
      {children}
      {rightIcon}
    </Link>
  );
}

export interface IconButtonProps extends Omit<ButtonProps, 'size' | 'leftIcon'> {
  /** Required: an icon-only control needs an accessible name. */
  label: string;
  icon: React.ReactNode;
  size?: 'sm' | 'md';
}

export function IconButton({
  label,
  icon,
  variant = 'ghost',
  size = 'md',
  className,
  ...props
}: IconButtonProps) {
  return (
    <Button
      variant={variant}
      size="icon"
      aria-label={label}
      title={label}
      className={cn(size === 'sm' && 'h-8 w-8', 'rounded-lg', className)}
      {...props}
    >
      {icon}
    </Button>
  );
}
