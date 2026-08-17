import { cn } from '@/lib/utils';

export type BadgeTone =
  | 'neutral'
  | 'brand'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info';

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-navy-100 text-navy-700 ring-navy-200',
  brand: 'bg-ieee-50 text-ieee-700 ring-ieee-200',
  success: 'bg-success-50 text-success-700 ring-success-100',
  warning: 'bg-warning-50 text-warning-700 ring-warning-100',
  danger: 'bg-danger-50 text-danger-700 ring-danger-100',
  info: 'bg-ieee-50 text-ieee-700 ring-ieee-100',
};

const DOTS: Record<BadgeTone, string> = {
  neutral: 'bg-navy-400',
  brand: 'bg-ieee-600',
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  danger: 'bg-danger-500',
  info: 'bg-ieee-500',
};

interface BadgeProps {
  children: React.ReactNode;
  tone?: BadgeTone;
  /** Adds a status dot so state is not communicated by colour alone. */
  dot?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

export function Badge({
  children,
  tone = 'neutral',
  dot = false,
  size = 'md',
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset',
        size === 'sm' ? 'px-2 py-0.5 text-2xs' : 'px-2.5 py-1 text-xs',
        TONES[tone],
        className,
      )}
    >
      {dot && (
        <span className={cn('h-1.5 w-1.5 rounded-full', DOTS[tone])} aria-hidden="true" />
      )}
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: 'published' | 'draft' | 'archived' }) {
  const config = {
    published: { tone: 'success' as const, label: 'Published' },
    draft: { tone: 'warning' as const, label: 'Draft' },
    archived: { tone: 'neutral' as const, label: 'Archived' },
  }[status];

  return (
    <Badge tone={config.tone} dot>
      {config.label}
    </Badge>
  );
}

export function RoleBadge({ role }: { role: string }) {
  const tone: BadgeTone =
    role === 'SUPER_ADMIN'
      ? 'danger'
      : role === 'ADMIN'
        ? 'brand'
        : role === 'EDITOR'
          ? 'info'
          : 'neutral';
  const label =
    { SUPER_ADMIN: 'Super admin', ADMIN: 'Admin', EDITOR: 'Editor', USER: 'Member' }[
      role
    ] ?? role;

  return (
    <Badge tone={tone} size="sm">
      {label}
    </Badge>
  );
}
