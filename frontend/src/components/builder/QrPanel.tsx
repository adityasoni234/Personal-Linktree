import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Download,
  ImagePlus,
  Info,
  Loader2,
  QrCode,
  RotateCcw,
  Trash2,
} from 'lucide-react';

import { ApiError } from '@/api/client';
import { mediaApi, qrApi } from '@/api/endpoints';
import type { QRConfig, QRPreset, QRRenderInfo } from '@/api/types';
import {
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  ColorField,
  RangeField,
  Select,
  Switch,
  Input,
  Skeleton,
} from '@/components/ui';
import { useDebounced } from '@/hooks';
import { cn, downloadBlob } from '@/lib/utils';
import { toast } from '@/stores/toast';

const DOT_STYLES = [
  { value: 'square', label: 'Square' },
  { value: 'rounded', label: 'Rounded' },
  { value: 'dot', label: 'Dots' },
  { value: 'classy', label: 'Classy' },
  { value: 'diamond', label: 'Diamond' },
  { value: 'vertical', label: 'Vertical bars' },
  { value: 'horizontal', label: 'Horizontal bars' },
];

const EYE_FRAMES = [
  { value: 'square', label: 'Square' },
  { value: 'rounded', label: 'Rounded' },
  { value: 'circle', label: 'Circle' },
  { value: 'leaf', label: 'Leaf' },
  { value: 'shield', label: 'Shield' },
];

const EYE_BALLS = [
  { value: 'square', label: 'Square' },
  { value: 'rounded', label: 'Rounded' },
  { value: 'circle', label: 'Circle' },
  { value: 'diamond', label: 'Diamond' },
];

const GRADIENTS = [
  { value: 'none', label: 'None' },
  { value: 'linear', label: 'Linear' },
  { value: 'radial', label: 'Radial' },
];

const ERROR_LEVELS = [
  { value: 'L', label: 'L — 7% recovery (smallest)' },
  { value: 'M', label: 'M — 15% recovery' },
  { value: 'Q', label: 'Q — 25% recovery (recommended)' },
  { value: 'H', label: 'H — 30% recovery (required with a logo)' },
];

const FRAMES = [
  { value: 'none', label: 'No frame' },
  { value: 'simple', label: 'Simple border' },
  { value: 'rounded', label: 'Rounded border' },
  { value: 'banner_bottom', label: 'Caption below' },
  { value: 'banner_top', label: 'Caption above' },
  { value: 'ticket', label: 'Ticket' },
];

interface QrPanelProps {
  groupId: string | null;
  config: QRConfig;
  onChange: (patch: Partial<QRConfig>) => void;
  render: QRRenderInfo | null;
  presets: QRPreset[];
  logoUrl: string | null;
  onLogoChange: (mediaId: string | null, url: string | null) => void;
  groupSlug: string;
}

export function QrPanel({
  groupId,
  config,
  onChange,
  render,
  presets,
  logoUrl,
  onLogoChange,
  groupSlug,
}: QrPanelProps) {
  const [preview, setPreview] = useState<QRRenderInfo | null>(render);
  const [isRendering, setIsRendering] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [downloading, setDownloading] = useState<'png' | 'svg' | null>(null);
  const previewToken = useRef(0);

  // Debounced so dragging a colour slider does not fire a render per frame.
  const debouncedConfig = useDebounced(config, 450);
  const configKey = useMemo(() => JSON.stringify(debouncedConfig), [debouncedConfig]);

  useEffect(() => {
    if (!groupId) return;
    const token = ++previewToken.current;
    setIsRendering(true);

    qrApi
      .preview(groupId, { ...debouncedConfig, size: 512 })
      .then((result) => {
        if (token === previewToken.current) setPreview(result);
      })
      .catch((error) => {
        if (token !== previewToken.current) return;
        if (error instanceof ApiError && error.code === 'QR_NOT_SCANNABLE') {
          // Keep the previous image on screen and explain why it did not update.
          setPreview((current) =>
            current
              ? {
                  ...current,
                  is_scannable: false,
                  warnings: [
                    { field: 'foreground_color', severity: 'error', message: error.message },
                  ],
                }
              : current,
          );
        }
      })
      .finally(() => {
        if (token === previewToken.current) setIsRendering(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configKey, groupId]);

  const handleLogoUpload = async (file: File) => {
    setUploading(true);
    try {
      const media = await mediaApi.upload(file, 'QR_LOGO');
      onLogoChange(media.id, media.public_url);
      onChange({ logo_media_id: media.id, error_correction: 'H' });
      toast.success('Logo added', 'Error correction raised to level H automatically.');
    } catch (error) {
      toast.error(
        'Upload failed',
        error instanceof Error ? error.message : 'Please try a different image.',
      );
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (format: 'png' | 'svg') => {
    if (!groupId) return;
    setDownloading(format);
    try {
      const blob = await qrApi.download(groupId, format, format === 'png' ? 1024 : 1024);
      downloadBlob(blob, `${groupSlug || 'group'}-qr.${format}`);
      toast.success(`${format.toUpperCase()} downloaded`);
    } catch {
      toast.error('Download failed', 'Save the group first, then try again.');
    } finally {
      setDownloading(null);
    }
  };

  const warnings = preview?.warnings ?? [];
  const blocking = warnings.filter((item) => item.severity === 'error');

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_20rem]">
      <div className="space-y-6 xl:order-1">
        <Card>
          <CardHeader
            title="Presets"
            description="A designed starting point, all contrast-checked"
            icon={<QrCode className="h-4 w-4" aria-hidden="true" />}
          />
          <CardBody>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => onChange({ ...(preset.config as Partial<QRConfig>), preset: preset.id })}
                  aria-pressed={config.preset === preset.id}
                  className={cn(
                    'rounded-xl border p-3 text-left transition',
                    config.preset === preset.id
                      ? 'border-ieee-600 ring-2 ring-ieee-600/25'
                      : 'border-navy-200 hover:border-navy-300',
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className="h-6 w-6 rounded"
                      style={{
                        backgroundColor:
                          (preset.config.background_color as string) ?? '#FFFFFF',
                        border: '1px solid rgba(11,37,69,0.12)',
                      }}
                    >
                      <span
                        className="m-1 block h-4 w-4 rounded-sm"
                        style={{
                          backgroundColor:
                            (preset.config.foreground_color as string) ?? '#00629B',
                        }}
                      />
                    </span>
                    <span className="text-sm font-medium text-navy-900">{preset.label}</span>
                  </span>
                  <span className="mt-1 block text-2xs text-navy-500 text-pretty">
                    {preset.description}
                  </span>
                </button>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Colours" />
          <CardBody className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <ColorField
                label="Foreground"
                value={config.foreground_color}
                onChange={(value) => onChange({ foreground_color: value, preset: null })}
              />
              <ColorField
                label="Background"
                value={config.background_color}
                onChange={(value) => onChange({ background_color: value, preset: null })}
                disabled={config.transparent_background}
              />
            </div>

            <Switch
              label="Transparent background"
              description="Best for placing the code over artwork. Always test-scan on the final surface."
              checked={config.transparent_background}
              onChange={(value) => onChange({ transparent_background: value })}
            />

            <Select
              label="Gradient"
              options={GRADIENTS}
              value={config.gradient_type}
              onChange={(event) =>
                onChange({
                  gradient_type: event.target.value as QRConfig['gradient_type'],
                  gradient_start_color:
                    event.target.value === 'none'
                      ? null
                      : (config.gradient_start_color ?? config.foreground_color),
                  gradient_end_color:
                    event.target.value === 'none'
                      ? null
                      : (config.gradient_end_color ?? '#0B2545'),
                  preset: null,
                })
              }
            />

            {config.gradient_type !== 'none' && (
              <div className="grid gap-4 sm:grid-cols-2">
                <ColorField
                  label="Gradient start"
                  value={config.gradient_start_color ?? config.foreground_color}
                  onChange={(value) => onChange({ gradient_start_color: value })}
                />
                <ColorField
                  label="Gradient end"
                  value={config.gradient_end_color ?? '#0B2545'}
                  onChange={(value) => onChange({ gradient_end_color: value })}
                />
                {config.gradient_type === 'linear' && (
                  <RangeField
                    label="Angle"
                    min={0}
                    max={360}
                    value={config.gradient_angle}
                    onChange={(value) => onChange({ gradient_angle: value })}
                    format={(value) => `${value}°`}
                  />
                )}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <ColorField
                label="Finder frame"
                value={config.eye_color ?? config.foreground_color}
                onChange={(value) => onChange({ eye_color: value, preset: null })}
              />
              <ColorField
                label="Finder centre"
                value={config.eye_ball_color ?? config.eye_color ?? config.foreground_color}
                onChange={(value) => onChange({ eye_ball_color: value, preset: null })}
              />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Shapes" />
          <CardBody className="grid gap-4 sm:grid-cols-3">
            <Select
              label="Module style"
              options={DOT_STYLES}
              value={config.dot_style}
              onChange={(event) =>
                onChange({ dot_style: event.target.value as QRConfig['dot_style'], preset: null })
              }
            />
            <Select
              label="Finder frame"
              options={EYE_FRAMES}
              value={config.eye_frame_style}
              onChange={(event) =>
                onChange({
                  eye_frame_style: event.target.value as QRConfig['eye_frame_style'],
                  preset: null,
                })
              }
            />
            <Select
              label="Finder centre"
              options={EYE_BALLS}
              value={config.eye_ball_style}
              onChange={(event) =>
                onChange({
                  eye_ball_style: event.target.value as QRConfig['eye_ball_style'],
                  preset: null,
                })
              }
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Logo" description="Placed in the centre, over cleared modules" />
          <CardBody className="space-y-5">
            <div className="flex items-center gap-4">
              {logoUrl ? (
                <img
                  src={logoUrl}
                  alt="QR logo preview"
                  className="h-16 w-16 rounded-xl object-contain ring-1 ring-navy-200"
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
                  {logoUrl ? 'Replace logo' : 'Upload logo'}
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
                {logoUrl && (
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<Trash2 className="h-4 w-4" />}
                    onClick={() => {
                      onLogoChange(null, null);
                      onChange({ logo_media_id: null });
                    }}
                  >
                    Remove
                  </Button>
                )}
              </div>
            </div>

            {logoUrl && (
              <>
                <RangeField
                  label="Logo size"
                  min={0.1}
                  max={0.3}
                  step={0.01}
                  value={config.logo_size}
                  onChange={(value) => onChange({ logo_size: value })}
                  format={(value) => `${Math.round(value * 100)}%`}
                  hint="Above 22% the code becomes unreliable even with maximum error correction."
                />
                <RangeField
                  label="Clear space around the logo"
                  min={0}
                  max={0.1}
                  step={0.01}
                  value={config.logo_padding}
                  onChange={(value) => onChange({ logo_padding: value })}
                  format={(value) => `${Math.round(value * 100)}%`}
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Select
                    label="Logo shape"
                    options={[
                      { value: 'square', label: 'Square' },
                      { value: 'rounded', label: 'Rounded' },
                      { value: 'circle', label: 'Circle' },
                    ]}
                    value={config.logo_shape}
                    onChange={(event) =>
                      onChange({ logo_shape: event.target.value as QRConfig['logo_shape'] })
                    }
                  />
                  <div className="flex items-end pb-1">
                    <Switch
                      label="Backdrop behind logo"
                      checked={config.logo_background}
                      onChange={(value) => onChange({ logo_background: value })}
                    />
                  </div>
                </div>
              </>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Frame &amp; caption" />
          <CardBody className="space-y-4">
            <Select
              label="Frame"
              options={FRAMES}
              value={config.frame_style}
              onChange={(event) =>
                onChange({
                  frame_style: event.target.value as QRConfig['frame_style'],
                  preset: null,
                })
              }
            />
            {config.frame_style !== 'none' && (
              <>
                <Input
                  label="Caption"
                  placeholder="SCAN ME"
                  maxLength={48}
                  value={config.caption ?? ''}
                  onChange={(event) => onChange({ caption: event.target.value || null })}
                  trailing={`${(config.caption ?? '').length}/48`}
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <ColorField
                    label="Frame colour"
                    value={config.frame_color}
                    onChange={(value) => onChange({ frame_color: value })}
                  />
                  <ColorField
                    label="Caption colour"
                    value={config.frame_text_color}
                    onChange={(value) => onChange({ frame_text_color: value })}
                  />
                </div>
              </>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Scanning" description="Trade design against reliability" />
          <CardBody className="space-y-4">
            <RangeField
              label="Quiet zone"
              min={0}
              max={12}
              value={config.margin}
              onChange={(value) => onChange({ margin: value })}
              format={(value) => `${value} modules`}
              hint="The empty border around the code. Below 2 modules many scanners fail to lock on."
            />
            <Select
              label="Error correction"
              options={ERROR_LEVELS}
              value={config.error_correction}
              onChange={(event) =>
                onChange({
                  error_correction: event.target.value as QRConfig['error_correction'],
                })
              }
              hint={
                config.logo_media_id
                  ? 'Forced to level H while a logo is in use.'
                  : 'Higher recovery makes the code denser but more forgiving of damage.'
              }
              disabled={Boolean(config.logo_media_id)}
            />
          </CardBody>
        </Card>
      </div>

      {/* ---- Sticky preview ---- */}
      <div className="xl:order-2">
        <div className="sticky top-6 space-y-4">
          <Card>
            <CardBody className="space-y-4">
              <div className="relative flex aspect-square items-center justify-center overflow-hidden rounded-xl border border-navy-200 bg-[conic-gradient(#F1F5F9_90deg,#FFFFFF_90deg_180deg,#F1F5F9_180deg_270deg,#FFFFFF_270deg)] bg-[length:16px_16px] p-4">
                {preview?.preview_data_uri ? (
                  <img
                    src={preview.preview_data_uri}
                    alt="QR code preview"
                    className="h-full w-full object-contain"
                  />
                ) : (
                  <Skeleton className="h-full w-full" />
                )}
                {isRendering && (
                  <span className="absolute right-2 top-2 rounded-full bg-white/90 p-1.5 shadow-card">
                    <Loader2 className="h-4 w-4 animate-spin text-ieee-600" aria-hidden="true" />
                  </span>
                )}
              </div>

              <div>
                <p className="text-2xs uppercase tracking-wide text-navy-400">Encodes</p>
                <p className="mt-0.5 break-all font-mono text-2xs text-navy-600">
                  {preview?.target_url ?? render?.target_url ?? '—'}
                </p>
                <p className="mt-2 text-2xs text-navy-500 text-pretty">
                  The code always points at this group's page — change the links behind it
                  whenever you like and printed codes keep working.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  isLoading={downloading === 'png'}
                  disabled={!groupId}
                  leftIcon={<Download className="h-4 w-4" />}
                  onClick={() => void handleDownload('png')}
                >
                  PNG
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  isLoading={downloading === 'svg'}
                  disabled={!groupId}
                  leftIcon={<Download className="h-4 w-4" />}
                  onClick={() => void handleDownload('svg')}
                >
                  SVG
                </Button>
              </div>
            </CardBody>
          </Card>

          {blocking.length > 0 && (
            <Callout
              tone="danger"
              title="This design will not scan"
              icon={<AlertTriangle className="h-4 w-4" aria-hidden="true" />}
            >
              <ul className="space-y-1">
                {blocking.map((warning) => (
                  <li key={warning.field}>{warning.message}</li>
                ))}
              </ul>
            </Callout>
          )}

          {warnings
            .filter((warning) => warning.severity !== 'error')
            .map((warning) => (
              <Callout
                key={`${warning.field}-${warning.message}`}
                tone={warning.severity === 'warning' ? 'warning' : 'info'}
                icon={
                  warning.severity === 'warning' ? (
                    <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Info className="h-4 w-4" aria-hidden="true" />
                  )
                }
              >
                {warning.message}
              </Callout>
            ))}

          {preview && blocking.length === 0 && (
            <p className="flex items-center gap-2 px-1 text-2xs text-navy-500">
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Contrast {preview.contrast_ratio}:1 — always test-scan before printing.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
