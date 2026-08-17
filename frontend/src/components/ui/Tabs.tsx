import { cn } from '@/lib/utils';

export interface TabItem<T extends string = string> {
  id: T;
  label: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  variant?: 'underline' | 'pill';
  className?: string;
  'aria-label'?: string;
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  variant = 'underline',
  className,
  'aria-label': ariaLabel = 'Sections',
}: TabsProps<T>) {
  const onKeyDown = (event: React.KeyboardEvent) => {
    const index = tabs.findIndex((tab) => tab.id === value);
    if (index < 0) return;

    // Arrow-key navigation is expected of a tablist.
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      const delta = event.key === 'ArrowRight' ? 1 : -1;
      const next = tabs[(index + delta + tabs.length) % tabs.length];
      if (next) onChange(next.id);
    }
  };

  if (variant === 'pill') {
    return (
      <div
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        className={cn(
          'inline-flex items-center gap-1 rounded-xl bg-navy-100 p-1',
          className,
        )}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={value === tab.id}
            tabIndex={value === tab.id ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition',
              value === tab.id
                ? 'bg-white text-navy-900 shadow-card'
                : 'text-navy-600 hover:text-navy-900',
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className={cn('scroll-x border-b border-navy-200', className)}>
      <div role="tablist" aria-label={ariaLabel} onKeyDown={onKeyDown} className="flex gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={value === tab.id}
            tabIndex={value === tab.id ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={cn(
              'relative inline-flex shrink-0 items-center gap-2 px-3.5 py-2.5 text-sm font-medium transition',
              'after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:transition',
              value === tab.id
                ? 'text-ieee-700 after:bg-ieee-600'
                : 'text-navy-500 hover:text-navy-800 after:bg-transparent',
            )}
          >
            {tab.icon}
            {tab.label}
            {tab.badge !== undefined && (
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-2xs font-semibold tabular-nums',
                  value === tab.id
                    ? 'bg-ieee-100 text-ieee-700'
                    : 'bg-navy-100 text-navy-600',
                )}
              >
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
