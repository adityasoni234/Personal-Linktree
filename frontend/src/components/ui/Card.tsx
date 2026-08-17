import { cn } from '@/lib/utils';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  as?: 'div' | 'section' | 'article';
  interactive?: boolean;
}

export function Card({ as: Tag = 'div', interactive, className, ...props }: CardProps) {
  return (
    <Tag
      className={cn(
        'rounded-2xl border border-navy-200/70 bg-white shadow-card',
        interactive &&
          'transition-shadow duration-200 hover:border-navy-200 hover:shadow-card-hover',
        className,
      )}
      {...props}
    />
  );
}

interface CardHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  /** Heading level — pick the one that fits the page outline. */
  as?: 'h2' | 'h3' | 'h4';
}

export function CardHeader({
  title,
  description,
  action,
  icon,
  className,
  as: Heading = 'h3',
}: CardHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 border-b border-navy-200/70 px-5 py-4',
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon && (
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ieee-50 text-ieee-600">
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <Heading className="truncate text-base font-semibold text-navy-900">
            {title}
          </Heading>
          {description && (
            <p className="mt-0.5 text-sm text-navy-500 text-pretty">{description}</p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5', className)} {...props} />;
}

export function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-end gap-2 border-t border-navy-200/70 bg-surface-subtle/60 px-5 py-3.5 rounded-b-2xl',
        className,
      )}
      {...props}
    />
  );
}

/* -------------------------------------------------------------------------- */
/* Stat tile                                                                  */
/* -------------------------------------------------------------------------- */

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  hint?: string;
  trend?: { value: number; label?: string } | null;
  isLoading?: boolean;
  className?: string;
}

export function StatCard({
  label,
  value,
  icon,
  hint,
  trend,
  isLoading,
  className,
}: StatCardProps) {
  return (
    <Card className={cn('p-5', className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-navy-500">{label}</p>
        {icon && (
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ieee-50 text-ieee-600">
            {icon}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="mt-3 h-9 w-24 animate-pulse rounded-lg bg-navy-100" />
      ) : (
        <p className="mt-2 font-display text-3xl font-semibold tabular-nums text-navy-900">
          {value}
        </p>
      )}

      {(hint || trend) && (
        <div className="mt-2 flex items-center gap-2 text-sm">
          {trend && (
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                trend.value >= 0
                  ? 'bg-success-50 text-success-700'
                  : 'bg-danger-50 text-danger-700',
              )}
            >
              {/* Direction is carried by the arrow glyph as well as the colour,
                  so it does not rely on colour alone. */}
              <span aria-hidden="true">{trend.value >= 0 ? '↑' : '↓'}</span>
              {Math.abs(trend.value)}%
              <span className="sr-only">
                {trend.value >= 0 ? 'increase' : 'decrease'}
              </span>
            </span>
          )}
          {(trend?.label ?? hint) && (
            <span className="text-navy-500">{trend?.label ?? hint}</span>
          )}
        </div>
      )}
    </Card>
  );
}
