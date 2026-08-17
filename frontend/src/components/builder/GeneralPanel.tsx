import { useEffect, useState } from 'react';
import { Check, Globe, ImagePlus, Loader2, Trash2, X } from 'lucide-react';

import { groupsApi, mediaApi } from '@/api/endpoints';
import type { GroupDetail } from '@/api/types';
import { Button, Callout, Card, CardBody, CardHeader, Input, Textarea } from '@/components/ui';
import { useDebounced } from '@/hooks';
import { cn, slugify } from '@/lib/utils';
import { toast } from '@/stores/toast';

const PUBLIC_BASE = (import.meta.env.VITE_PUBLIC_BASE_URL ?? window.location.origin).replace(
  /\/$/,
  '',
);

export interface GeneralDraft {
  name: string;
  slug: string;
  description: string;
  logo_url: string | null;
  seo_title: string;
  seo_description: string;
}

interface GeneralPanelProps {
  draft: GeneralDraft;
  onChange: (patch: Partial<GeneralDraft>) => void;
  existing: GroupDetail | null;
  errors: Partial<Record<keyof GeneralDraft, string>>;
}

export function GeneralPanel({ draft, onChange, existing, errors }: GeneralPanelProps) {
  const [slugTouched, setSlugTouched] = useState(Boolean(existing));
  const [uploading, setUploading] = useState(false);
  const debouncedSlug = useDebounced(draft.slug, 400);
  const [availability, setAvailability] = useState<{
    checking: boolean;
    available: boolean | null;
    reason: string | null;
  }>({ checking: false, available: null, reason: null });

  // Keep the slug in step with the name until the author edits it themselves.
  useEffect(() => {
    if (!slugTouched) onChange({ slug: slugify(draft.name) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.name, slugTouched]);

  useEffect(() => {
    if (!debouncedSlug || debouncedSlug.length < 3) {
      setAvailability({ checking: false, available: null, reason: null });
      return;
    }
    if (existing && debouncedSlug === existing.slug) {
      setAvailability({ checking: false, available: true, reason: null });
      return;
    }

    let cancelled = false;
    setAvailability((state) => ({ ...state, checking: true }));
    groupsApi
      .checkSlug(debouncedSlug, existing?.id)
      .then((result) => {
        if (cancelled) return;
        setAvailability({
          checking: false,
          available: result.available,
          reason: result.reason,
        });
      })
      .catch(() => {
        if (!cancelled) setAvailability({ checking: false, available: null, reason: null });
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedSlug, existing]);

  const handleLogoUpload = async (file: File) => {
    setUploading(true);
    try {
      const media = await mediaApi.upload(file, 'GROUP_LOGO');
      onChange({ logo_url: media.public_url });
      toast.success('Logo uploaded');
    } catch (error) {
      toast.error(
        'Upload failed',
        error instanceof Error ? error.message : 'Please try a different image.',
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Group details"
          description="How this group appears on its public page"
          icon={<Globe className="h-4 w-4" aria-hidden="true" />}
        />
        <CardBody className="space-y-5">
          <Input
            label="Group name"
            required
            placeholder="Computer Society"
            value={draft.name}
            error={errors.name}
            onChange={(event) => onChange({ name: event.target.value })}
            trailing={`${draft.name.length}/120`}
            maxLength={120}
          />

          <div>
            <Input
              label="Public address"
              required
              value={draft.slug}
              error={errors.slug}
              onChange={(event) => {
                setSlugTouched(true);
                onChange({ slug: event.target.value.toLowerCase() });
              }}
              className="font-mono"
              maxLength={48}
              rightSlot={
                availability.checking ? (
                  <span className="px-2">
                    <Loader2 className="h-4 w-4 animate-spin text-navy-400" aria-hidden="true" />
                  </span>
                ) : availability.available === true ? (
                  <span className="px-2" title="Available">
                    <Check className="h-4 w-4 text-success-600" aria-hidden="true" />
                  </span>
                ) : availability.available === false ? (
                  <span className="px-2" title="Not available">
                    <X className="h-4 w-4 text-danger-600" aria-hidden="true" />
                  </span>
                ) : undefined
              }
            />
            <p className="mt-1.5 flex flex-wrap items-center gap-1 text-sm text-navy-500">
              <span>Visitors will land on</span>
              <code className="rounded bg-navy-100 px-1.5 py-0.5 font-mono text-2xs text-navy-700">
                {PUBLIC_BASE}/g/{draft.slug || 'your-address'}
              </code>
            </p>
            {availability.available === false && availability.reason && (
              <p className="mt-1 text-sm text-danger-600" role="alert">
                {availability.reason}
              </p>
            )}
            {existing && draft.slug !== existing.slug && (
              <Callout tone="warning" className="mt-3">
                Changing the address breaks any QR code or link that has already been shared
                with the old one. The QR image itself keeps working — it points at whatever
                address this group has — but printed material showing the old URL will not.
              </Callout>
            )}
          </div>

          <Textarea
            label="Description"
            placeholder="What is this group about? One or two lines is plenty."
            value={draft.description}
            error={errors.description}
            onChange={(event) => onChange({ description: event.target.value })}
            trailing={`${draft.description.length}/500`}
            maxLength={500}
            rows={3}
          />

          <div>
            <p className="mb-1.5 text-sm font-medium text-navy-800">Logo</p>
            <div className="flex items-center gap-4">
              {draft.logo_url ? (
                <img
                  src={draft.logo_url}
                  alt="Group logo preview"
                  className="h-16 w-16 rounded-xl object-cover ring-1 ring-navy-200"
                />
              ) : (
                <span className="flex h-16 w-16 items-center justify-center rounded-xl bg-navy-100 text-navy-400">
                  <ImagePlus className="h-6 w-6" aria-hidden="true" />
                </span>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <label
                  className={cn(
                    'inline-flex h-10 cursor-pointer items-center gap-2 rounded-xl border border-navy-200 bg-white px-4 text-sm font-medium text-navy-800 shadow-card transition hover:bg-surface-subtle',
                    uploading && 'pointer-events-none opacity-60',
                  )}
                >
                  {uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <ImagePlus className="h-4 w-4" aria-hidden="true" />
                  )}
                  {draft.logo_url ? 'Replace' : 'Upload'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/svg+xml"
                    className="sr-only"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void handleLogoUpload(file);
                      event.target.value = '';
                    }}
                  />
                </label>

                {draft.logo_url && (
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<Trash2 className="h-4 w-4" />}
                    onClick={() => onChange({ logo_url: null })}
                  >
                    Remove
                  </Button>
                )}
              </div>
            </div>
            <p className="mt-2 text-sm text-navy-500">
              PNG, JPG, WEBP or SVG, up to 2 MB. Images are re-encoded on upload and SVGs are
              sanitised.
            </p>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Search &amp; social preview"
          description="Controls the title and description shown when the page is shared"
        />
        <CardBody className="space-y-5">
          <Input
            label="Page title"
            placeholder={draft.name ? `${draft.name} · IEEE SOU` : 'Leave blank to use the group name'}
            value={draft.seo_title}
            onChange={(event) => onChange({ seo_title: event.target.value })}
            trailing={`${draft.seo_title.length}/70`}
            maxLength={70}
          />
          <Textarea
            label="Meta description"
            placeholder="A one-line summary for search results and link previews."
            value={draft.seo_description}
            onChange={(event) => onChange({ seo_description: event.target.value })}
            trailing={`${draft.seo_description.length}/200`}
            maxLength={200}
            rows={2}
          />

          {/* A concrete preview beats an abstract description of what these do. */}
          <div className="rounded-xl border border-navy-200 bg-surface-subtle p-4">
            <p className="text-2xs uppercase tracking-wide text-navy-400">Search preview</p>
            <p className="mt-2 truncate text-base text-ieee-700">
              {draft.seo_title || draft.name || 'Your group'}
            </p>
            <p className="truncate text-xs text-success-700">
              {PUBLIC_BASE}/g/{draft.slug || 'your-address'}
            </p>
            <p className="mt-1 line-clamp-2 text-sm text-navy-600">
              {draft.seo_description ||
                draft.description ||
                `All the official links for ${draft.name || 'your group'}.`}
            </p>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
