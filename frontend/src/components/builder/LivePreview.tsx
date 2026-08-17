import { Monitor, Smartphone } from 'lucide-react';
import { useState } from 'react';

import type { PublicLink, Theme } from '@/api/types';
import { PublicPageView } from '@/components/public/PublicPageView';
import { cn } from '@/lib/utils';

interface LivePreviewProps {
  name: string;
  description?: string | null;
  logoUrl?: string | null;
  organizationName?: string;
  theme: Theme;
  links: PublicLink[];
  className?: string;
}

/**
 * Live preview of the public page.
 *
 * Renders the same `PublicPageView` visitors see, inside a device frame — so
 * there is no second implementation of the page that can drift from the real one.
 */
export function LivePreview({
  name,
  description,
  logoUrl,
  organizationName,
  theme,
  links,
  className,
}: LivePreviewProps) {
  const [device, setDevice] = useState<'mobile' | 'desktop'>('mobile');

  return (
    <div className={cn('flex flex-col', className)}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-navy-900">Live preview</h2>
        <div
          className="inline-flex items-center gap-1 rounded-lg bg-navy-100 p-0.5"
          role="group"
          aria-label="Preview device"
        >
          {(
            [
              { id: 'mobile' as const, icon: Smartphone, label: 'Mobile' },
              { id: 'desktop' as const, icon: Monitor, label: 'Desktop' },
            ]
          ).map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setDevice(option.id)}
              aria-pressed={device === option.id}
              aria-label={`${option.label} preview`}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition',
                device === option.id
                  ? 'bg-white text-navy-900 shadow-card'
                  : 'text-navy-500 hover:text-navy-800',
              )}
            >
              <option.icon className="h-3.5 w-3.5" aria-hidden="true" />
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-1 items-start justify-center rounded-2xl border border-navy-200/70 bg-surface-muted p-5">
        {device === 'mobile' ? (
          <div className="relative w-[19rem] max-w-full">
            {/* Device frame */}
            <div className="overflow-hidden rounded-[2.25rem] border-[10px] border-navy-900 bg-navy-900 shadow-panel">
              <div className="relative h-[38rem] overflow-y-auto bg-white">
                <span className="pointer-events-none absolute left-1/2 top-2 z-10 h-5 w-24 -translate-x-1/2 rounded-full bg-navy-900" />
                <PublicPageView
                  name={name || 'Your group name'}
                  description={description}
                  logoUrl={logoUrl}
                  organizationName={organizationName}
                  theme={theme}
                  links={links}
                  isPreview
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="w-full overflow-hidden rounded-xl border border-navy-200 bg-white shadow-card">
            <div className="flex items-center gap-1.5 border-b border-navy-200 bg-surface-subtle px-3 py-2">
              {['#EF4444', '#F59E0B', '#10B981'].map((color) => (
                <span
                  key={color}
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
            <div className="h-[34rem] overflow-y-auto">
              <PublicPageView
                name={name || 'Your group name'}
                description={description}
                logoUrl={logoUrl}
                organizationName={organizationName}
                theme={theme}
                links={links}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
