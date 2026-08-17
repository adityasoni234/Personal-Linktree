import { useState } from 'react';
import { MoreHorizontal } from 'lucide-react';

import { useDismissable } from '@/hooks';
import { cn } from '@/lib/utils';

export interface MenuItem {
  label: string;
  icon?: React.ReactNode;
  onSelect: () => void;
  tone?: 'default' | 'danger';
  disabled?: boolean;
  /** Renders a divider above this item. */
  separated?: boolean;
}

interface MenuProps {
  items: MenuItem[];
  label?: string;
  trigger?: React.ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export function Menu({
  items,
  label = 'More actions',
  trigger,
  align = 'right',
  className,
}: MenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useDismissable<HTMLDivElement>(open, () => setOpen(false));

  if (items.length === 0) return null;

  return (
    <div ref={ref} className={cn('relative', className)}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-navy-500 transition hover:bg-navy-100 hover:text-navy-800 focus-visible:ring-2 focus-visible:ring-ieee-600 focus-visible:ring-offset-2"
      >
        {trigger ?? <MoreHorizontal className="h-5 w-5" aria-hidden="true" />}
      </button>

      {open && (
        <div
          role="menu"
          className={cn(
            'absolute z-30 mt-1.5 min-w-[12rem] animate-slide-up overflow-hidden rounded-xl border border-navy-200/70 bg-white p-1 shadow-panel',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {items.map((item, index) => (
            <div key={`${item.label}-${index}`}>
              {item.separated && <div className="my-1 h-px bg-navy-100" />}
              <button
                type="button"
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  setOpen(false);
                  item.onSelect();
                }}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition',
                  'disabled:cursor-not-allowed disabled:opacity-45',
                  item.tone === 'danger'
                    ? 'text-danger-600 hover:bg-danger-50'
                    : 'text-navy-700 hover:bg-navy-100 hover:text-navy-900',
                )}
              >
                {item.icon && <span className="shrink-0">{item.icon}</span>}
                {item.label}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
