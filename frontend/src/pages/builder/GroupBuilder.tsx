import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  BarChart3,
  ExternalLink,
  Eye,
  Link2,
  Palette,
  QrCode,
  Save,
  Settings2,
  Share2,
} from 'lucide-react';

import { ApiError } from '@/api/client';
import { groupsApi, linksApi, qrApi } from '@/api/endpoints';
import type {
  GroupDetail,
  LinkItem,
  PublicLink,
  QRConfig,
  QRPreset,
  QRRenderInfo,
  Theme,
} from '@/api/types';
import { AppearancePanel } from '@/components/builder/AppearancePanel';
import { GeneralPanel, type GeneralDraft } from '@/components/builder/GeneralPanel';
import { LinksPanel } from '@/components/builder/LinksPanel';
import { LivePreview } from '@/components/builder/LivePreview';
import { QrPanel } from '@/components/builder/QrPanel';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Badge,
  Button,
  ErrorState,
  PageLoader,
  Switch,
  Tabs,
  type TabItem,
} from '@/components/ui';
import { useCopyToClipboard, useDocumentTitle } from '@/hooks';
import { slugify } from '@/lib/utils';
import { groupFormSchema } from '@/schemas';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/stores/toast';

type BuilderTab = 'general' | 'links' | 'appearance' | 'qr';

const TABS: TabItem<BuilderTab>[] = [
  { id: 'general', label: 'General', icon: <Settings2 className="h-4 w-4" /> },
  { id: 'links', label: 'Links', icon: <Link2 className="h-4 w-4" /> },
  { id: 'appearance', label: 'Appearance', icon: <Palette className="h-4 w-4" /> },
  { id: 'qr', label: 'QR code', icon: <QrCode className="h-4 w-4" /> },
];

const DEFAULT_THEME: Theme = {
  preset: 'ieee-classic',
  primary_color: '#00629B',
  secondary_color: '#0B2545',
  background_color: '#F5F7FA',
  background_end_color: null,
  background_style: 'solid',
  text_color: '#0B1F33',
  button_style: 'solid',
  button_radius: 'lg',
  font: 'inter',
};

const DEFAULT_QR: QRConfig = {
  preset: 'ieee-classic',
  foreground_color: '#00629B',
  background_color: '#FFFFFF',
  transparent_background: false,
  gradient_type: 'none',
  gradient_start_color: null,
  gradient_end_color: null,
  gradient_angle: 45,
  dot_style: 'square',
  eye_frame_style: 'square',
  eye_ball_style: 'square',
  eye_color: '#0B2545',
  eye_ball_color: '#00629B',
  margin: 4,
  error_correction: 'Q',
  logo_media_id: null,
  logo_size: 0.2,
  logo_padding: 0.04,
  logo_shape: 'rounded',
  logo_background: true,
  frame_style: 'none',
  frame_color: '#00629B',
  frame_text_color: '#FFFFFF',
  caption: null,
};

export function GroupBuilderPage() {
  const { groupId: routeId } = useParams<{ groupId: string }>();
  const isNew = !routeId;
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const { copy } = useCopyToClipboard();

  const [tab, setTab] = useState<BuilderTab>('general');
  const [groupId, setGroupId] = useState<string | null>(routeId ?? null);
  const [group, setGroup] = useState<GroupDetail | null>(null);
  const [links, setLinks] = useState<LinkItem[]>([]);
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME);
  const [qrConfig, setQrConfig] = useState<QRConfig>(DEFAULT_QR);
  const [qrRender, setQrRender] = useState<QRRenderInfo | null>(null);
  const [qrPresets, setQrPresets] = useState<QRPreset[]>([]);
  const [qrLogoUrl, setQrLogoUrl] = useState<string | null>(null);

  const [draft, setDraft] = useState<GeneralDraft>({
    name: '',
    slug: '',
    description: '',
    logo_url: null,
    seo_title: '',
    seo_description: '',
  });

  const [errors, setErrors] = useState<Partial<Record<keyof GeneralDraft, string>>>({});
  const [isLoading, setIsLoading] = useState(!isNew);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  useDocumentTitle(isNew ? 'New group' : (group?.name ?? 'Group builder'));

  /* ---- Load ------------------------------------------------------------ */
  const load = useCallback(async () => {
    if (!routeId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      const [detail, groupLinks, qr] = await Promise.all([
        groupsApi.get(routeId),
        linksApi.list(routeId),
        qrApi.get(routeId),
      ]);

      setGroup(detail);
      setGroupId(detail.id);
      setLinks(groupLinks);
      setTheme({ ...DEFAULT_THEME, ...detail.theme });
      setDraft({
        name: detail.name,
        slug: detail.slug,
        description: detail.description ?? '',
        logo_url: detail.logo_url,
        seo_title: detail.seo?.title ?? '',
        seo_description: detail.seo?.description ?? '',
      });

      const { id: _id, group_id: _groupId, logo_url, updated_at: _updated, ...config } = qr.config;
      setQrConfig({ ...DEFAULT_QR, ...config });
      setQrLogoUrl(logo_url);
      setQrRender(qr.render);
      setIsDirty(false);
    } catch (error) {
      setLoadError(
        error instanceof ApiError ? error : new ApiError(0, 'UNKNOWN', 'Could not load the group'),
      );
    } finally {
      setIsLoading(false);
    }
  }, [routeId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    qrApi.presets().then(setQrPresets).catch(() => setQrPresets([]));
  }, []);

  /* ---- Unsaved-changes guard ------------------------------------------ */
  useEffect(() => {
    if (!isDirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const patchDraft = (patch: Partial<GeneralDraft>) => {
    setDraft((current) => ({ ...current, ...patch }));
    setIsDirty(true);
  };

  const patchTheme = (patch: Partial<Theme>) => {
    setTheme((current) => ({ ...current, ...patch }));
    setIsDirty(true);
  };

  /* ---- Save ------------------------------------------------------------ */
  const validate = (): boolean => {
    const result = groupFormSchema.safeParse({
      name: draft.name,
      slug: draft.slug || slugify(draft.name),
      description: draft.description || undefined,
    });
    if (result.success) {
      setErrors({});
      return true;
    }
    const fieldErrors: Partial<Record<keyof GeneralDraft, string>> = {};
    for (const issue of result.error.issues) {
      const key = issue.path[0] as keyof GeneralDraft;
      if (key && !fieldErrors[key]) fieldErrors[key] = issue.message;
    }
    setErrors(fieldErrors);
    setTab('general');
    return false;
  };

  const save = async () => {
    if (!validate()) {
      toast.error('Check the highlighted fields');
      return;
    }
    setIsSaving(true);
    try {
      const payload = {
        name: draft.name.trim(),
        slug: draft.slug || slugify(draft.name),
        description: draft.description.trim() || null,
        logo_url: draft.logo_url,
        theme,
        seo: {
          title: draft.seo_title.trim() || null,
          description: draft.seo_description.trim() || null,
          og_image_url: draft.logo_url,
        },
      };

      let saved: GroupDetail;
      if (groupId) {
        saved = await groupsApi.update(groupId, payload);
      } else {
        saved = await groupsApi.create(payload);
        setGroupId(saved.id);
        // Move to the canonical URL so a refresh reloads the saved group.
        navigate(`/dashboard/groups/${saved.id}`, { replace: true });
      }

      // The QR design is stored separately from the group record.
      if (saved.id) {
        const qr = await qrApi.save(saved.id, qrConfig);
        setQrRender(qr.render);
        setQrLogoUrl(qr.config.logo_url);
      }

      setGroup(saved);
      setTheme({ ...DEFAULT_THEME, ...saved.theme });
      setDraft((current) => ({ ...current, slug: saved.slug }));
      setIsDirty(false);
      toast.success('Saved', saved.is_published ? 'Your changes are live.' : 'Saved as a draft.');
    } catch (error) {
      if (error instanceof ApiError) {
        const field = (error.details as { field?: string } | undefined)?.field;
        if (field === 'slug') {
          setErrors({ slug: error.message });
          setTab('general');
        }
        toast.error('Could not save', error.message);
      } else {
        toast.error('Could not save the group');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const togglePublished = async (next: boolean) => {
    if (!groupId) {
      toast.info('Save the group first', 'A group must be saved before it can be published.');
      return;
    }
    try {
      const updated = await groupsApi.setPublished(groupId, next);
      setGroup(updated);
      toast.success(
        next ? 'Group published' : 'Group unpublished',
        next ? updated.public_url : 'The public page is now offline.',
      );
    } catch (error) {
      toast.error(
        'Could not change visibility',
        error instanceof ApiError ? error.message : undefined,
      );
    }
  };

  /* ---- Preview data ---------------------------------------------------- */
  const previewLinks: PublicLink[] = useMemo(
    () =>
      links
        .filter((link) => link.is_active)
        .sort((first, second) => first.position - second.position)
        .map((link) => ({
          id: link.id,
          title: link.title,
          url: link.url,
          description: link.description,
          icon: link.icon,
          style: link.style,
        })),
    [links],
  );

  if (isLoading) return <PageLoader label="Loading group" />;
  if (loadError) return <ErrorState error={loadError} onRetry={load} />;

  return (
    <>
      <PageHeader
        breadcrumb={
          <Link
            to="/dashboard/groups"
            className="inline-flex items-center gap-1.5 text-sm text-navy-500 hover:text-ieee-600"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
            All groups
          </Link>
        }
        title={draft.name || 'New group'}
        description={
          group
            ? `Public address: ${group.public_url}`
            : 'Set up the page, add links, then publish when you are ready.'
        }
        actions={
          <>
            {group && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Share2 className="h-4 w-4" />}
                  onClick={() => {
                    void copy(group.public_url).then((ok) =>
                      ok ? toast.success('Link copied') : toast.error('Could not copy'),
                    );
                  }}
                >
                  Copy link
                </Button>
                {group.is_published && (
                  <a
                    href={group.public_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex h-9 items-center gap-2 rounded-xl px-3 text-sm font-medium text-navy-600 hover:bg-navy-100"
                  >
                    <ExternalLink className="h-4 w-4" aria-hidden="true" />
                    View live
                  </a>
                )}
              </>
            )}
            <Button
              onClick={() => void save()}
              isLoading={isSaving}
              leftIcon={<Save className="h-4 w-4" />}
            >
              {groupId ? 'Save changes' : 'Create group'}
            </Button>
          </>
        }
      />

      {group && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-navy-200/70 bg-white p-4 shadow-card">
          <div className="flex items-center gap-3">
            <Badge tone={group.is_published ? 'success' : 'warning'} dot>
              {group.is_published ? 'Published' : 'Draft'}
            </Badge>
            {isDirty && (
              <span className="text-2xs text-warning-700">Unsaved changes</span>
            )}
          </div>
          <Switch
            label="Publish this page"
            description={
              group.is_published
                ? 'Anyone with the link or QR code can view it.'
                : 'Only your organization can see this group.'
            }
            checked={group.is_published}
            onChange={(value) => void togglePublished(value)}
          />
        </div>
      )}

      {/* The QR tab carries its own sticky preview, so the page preview column
          is dropped there — otherwise its 22rem track would stay reserved and
          squeeze the designer. */}
      <div
        className={
          tab === 'qr'
            ? 'grid gap-6'
            : 'grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]'
        }
      >
        <div className="min-w-0">
          <Tabs
            tabs={TABS.map((item) =>
              item.id === 'links' ? { ...item, badge: links.length } : item,
            )}
            value={tab}
            onChange={setTab}
            aria-label="Group builder sections"
            className="mb-5"
          />

          {tab === 'general' && (
            <GeneralPanel draft={draft} onChange={patchDraft} existing={group} errors={errors} />
          )}

          {tab === 'links' && (
            <LinksPanel
              groupId={groupId}
              links={links}
              onChange={(next) => {
                setLinks(next);
              }}
            />
          )}

          {tab === 'appearance' && <AppearancePanel theme={theme} onChange={patchTheme} />}

          {tab === 'qr' && (
            <QrPanel
              groupId={groupId}
              config={qrConfig}
              onChange={(patch) => {
                setQrConfig((current) => ({ ...current, ...patch }));
                setIsDirty(true);
              }}
              render={qrRender}
              presets={qrPresets}
              logoUrl={qrLogoUrl}
              onLogoChange={(_mediaId, url) => setQrLogoUrl(url)}
              groupSlug={draft.slug}
            />
          )}
        </div>

        {/* The preview follows the editor on mobile and sits beside it on
            desktop, per the builder spec. */}
        {tab !== 'qr' && (
          <LivePreview
            className="xl:sticky xl:top-6 xl:self-start"
            name={draft.name}
            description={draft.description}
            logoUrl={draft.logo_url}
            organizationName={user?.organization_name ?? undefined}
            theme={theme}
            links={previewLinks}
          />
        )}
      </div>

      {group && (
        <div className="mt-6 flex flex-wrap items-center gap-3 rounded-2xl border border-navy-200/70 bg-white p-4 text-sm shadow-card">
          <BarChart3 className="h-4 w-4 text-navy-400" aria-hidden="true" />
          <span className="text-navy-600">
            {group.stats.page_views} views · {group.stats.qr_scans} scans ·{' '}
            {group.stats.link_clicks} clicks
          </span>
          <Link
            to="/dashboard/analytics"
            className="inline-flex items-center gap-1 font-medium text-ieee-600 hover:underline"
          >
            <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            Full analytics
          </Link>
        </div>
      )}
    </>
  );
}

export default GroupBuilderPage;
