import { Check, Palette, Type } from 'lucide-react';

import type { Theme } from '@/api/types';
import { Callout, Card, CardBody, CardHeader, ColorField, Select } from '@/components/ui';
import { cn } from '@/lib/utils';

/** Contrast ratio, used to warn about unreadable colour choices in the editor. */
function contrastRatio(foreground: string, background: string): number {
  const luminance = (hex: string) => {
    const value = hex.replace('#', '');
    if (value.length < 6) return 0;
    const channels = [0, 2, 4].map((offset) => {
      const srgb = parseInt(value.slice(offset, offset + 2), 16) / 255;
      return srgb <= 0.03928 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!;
  };
  const first = luminance(foreground);
  const second = luminance(background);
  const [lighter, darker] = first > second ? [first, second] : [second, first];
  return Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100;
}

interface ThemePresetDefinition {
  id: Theme['preset'];
  label: string;
  description: string;
  values: Partial<Theme>;
}

const THEME_PRESETS: ThemePresetDefinition[] = [
  {
    id: 'ieee-classic',
    label: 'IEEE Classic',
    description: 'IEEE blue on a soft grey field',
    values: {
      primary_color: '#00629B',
      secondary_color: '#0B2545',
      background_color: '#F5F7FA',
      background_style: 'solid',
      text_color: '#0B1F33',
      button_style: 'solid',
      button_radius: 'lg',
      font: 'inter',
    },
  },
  {
    id: 'minimal-white',
    label: 'Minimal White',
    description: 'Quiet, high-contrast, prints well',
    values: {
      primary_color: '#111827',
      secondary_color: '#374151',
      background_color: '#FFFFFF',
      background_style: 'solid',
      text_color: '#111827',
      button_style: 'outline',
      button_radius: 'md',
      font: 'inter',
    },
  },
  {
    id: 'dark',
    label: 'Dark',
    description: 'Deep navy with luminous buttons',
    values: {
      primary_color: '#00A3E0',
      secondary_color: '#00629B',
      background_color: '#0B2545',
      background_style: 'solid',
      text_color: '#FFFFFF',
      button_style: 'soft',
      button_radius: 'lg',
      font: 'inter',
    },
  },
  {
    id: 'corporate',
    label: 'Corporate',
    description: 'Restrained, professional, serif headings',
    values: {
      primary_color: '#014E7C',
      secondary_color: '#0B2545',
      background_color: '#F8FAFC',
      background_style: 'solid',
      text_color: '#0B1F33',
      button_style: 'solid',
      button_radius: 'sm',
      font: 'source-serif',
    },
  },
  {
    id: 'gradient',
    label: 'Gradient',
    description: 'Navy-to-blue wash with glass buttons',
    values: {
      primary_color: '#FFFFFF',
      secondary_color: '#00A3E0',
      background_color: '#0B2545',
      background_end_color: '#00629B',
      background_style: 'gradient',
      text_color: '#FFFFFF',
      button_style: 'glass',
      button_radius: 'full',
      font: 'space-grotesk',
    },
  },
  {
    id: 'event',
    label: 'Event',
    description: 'Bold and high-energy for launches',
    values: {
      primary_color: '#C2410C',
      secondary_color: '#0B2545',
      background_color: '#FFF7ED',
      background_style: 'pattern',
      text_color: '#1F1300',
      button_style: 'solid',
      button_radius: 'full',
      font: 'space-grotesk',
    },
  },
];

const BUTTON_STYLES = [
  { value: 'solid', label: 'Solid' },
  { value: 'outline', label: 'Outline' },
  { value: 'soft', label: 'Soft' },
  { value: 'glass', label: 'Glass' },
];

const RADII = [
  { value: 'none', label: 'Square' },
  { value: 'sm', label: 'Slight' },
  { value: 'md', label: 'Medium' },
  { value: 'lg', label: 'Rounded' },
  { value: 'full', label: 'Pill' },
];

const FONTS = [
  { value: 'inter', label: 'Inter — clean and neutral' },
  { value: 'space-grotesk', label: 'Space Grotesk — technical' },
  { value: 'dm-sans', label: 'DM Sans — friendly' },
  { value: 'source-serif', label: 'Source Serif — editorial' },
  { value: 'system', label: 'System default' },
];

const BACKGROUNDS = [
  { value: 'solid', label: 'Solid colour' },
  { value: 'gradient', label: 'Gradient' },
  { value: 'pattern', label: 'Subtle dots' },
];

interface AppearancePanelProps {
  theme: Theme;
  onChange: (patch: Partial<Theme>) => void;
}

export function AppearancePanel({ theme, onChange }: AppearancePanelProps) {
  const textColor = theme.text_color ?? '#0B1F33';
  const bodyContrast = contrastRatio(textColor, theme.background_color);
  const buttonContrast = contrastRatio('#FFFFFF', theme.primary_color);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Theme"
          description="Start from a preset, then adjust anything you like"
          icon={<Palette className="h-4 w-4" aria-hidden="true" />}
        />
        <CardBody>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {THEME_PRESETS.map((preset) => {
              const isActive = theme.preset === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => onChange({ preset: preset.id, ...preset.values })}
                  aria-pressed={isActive}
                  className={cn(
                    'group relative overflow-hidden rounded-xl border p-3 text-left transition',
                    isActive
                      ? 'border-ieee-600 ring-2 ring-ieee-600/25'
                      : 'border-navy-200 hover:border-navy-300',
                  )}
                >
                  <span
                    className="flex h-16 w-full items-end justify-start gap-1 rounded-lg p-2"
                    style={{
                      background:
                        preset.values.background_style === 'gradient'
                          ? `linear-gradient(160deg, ${preset.values.background_color}, ${preset.values.background_end_color})`
                          : preset.values.background_color,
                    }}
                  >
                    <span
                      className="h-4 w-2/3 rounded"
                      style={{ backgroundColor: preset.values.primary_color }}
                    />
                  </span>
                  <span className="mt-2 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-navy-900">{preset.label}</span>
                    {isActive && (
                      <Check className="h-4 w-4 text-ieee-600" aria-hidden="true" />
                    )}
                  </span>
                  <span className="mt-0.5 block text-2xs text-navy-500">
                    {preset.description}
                  </span>
                </button>
              );
            })}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Colours" description="Adjust the palette for this group" />
        <CardBody className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <ColorField
              label="Primary (buttons)"
              value={theme.primary_color}
              onChange={(value) => onChange({ primary_color: value })}
            />
            <ColorField
              label="Secondary (accents)"
              value={theme.secondary_color}
              onChange={(value) => onChange({ secondary_color: value })}
            />
            <ColorField
              label="Background"
              value={theme.background_color}
              onChange={(value) => onChange({ background_color: value })}
            />
            <ColorField
              label="Text"
              value={textColor}
              onChange={(value) => onChange({ text_color: value })}
            />
          </div>

          <Select
            label="Background style"
            options={BACKGROUNDS}
            value={theme.background_style}
            onChange={(event) =>
              onChange({ background_style: event.target.value as Theme['background_style'] })
            }
          />

          {theme.background_style === 'gradient' && (
            <ColorField
              label="Gradient end colour"
              value={theme.background_end_color ?? theme.primary_color}
              onChange={(value) => onChange({ background_end_color: value })}
            />
          )}

          {/* Contrast is checked here and again on the server, which will
              recompute a readable text colour if this one is unusable. */}
          {bodyContrast < 4.5 && (
            <Callout tone="warning" title="Body text may be hard to read">
              Text and background are only at {bodyContrast}:1. WCAG AA asks for 4.5:1 —
              the server will substitute a readable colour if this is saved as is.
            </Callout>
          )}
          {buttonContrast < 3 && theme.button_style === 'solid' && (
            <Callout tone="warning" title="Button labels may be hard to read">
              White text on your primary colour is only at {buttonContrast}:1. Try a darker
              primary colour, or switch to the outline button style.
            </Callout>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Buttons &amp; type"
          description="Shape and typography for the link list"
          icon={<Type className="h-4 w-4" aria-hidden="true" />}
        />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Button style"
            options={BUTTON_STYLES}
            value={theme.button_style}
            onChange={(event) =>
              onChange({ button_style: event.target.value as Theme['button_style'] })
            }
          />
          <Select
            label="Corner radius"
            options={RADII}
            value={theme.button_radius}
            onChange={(event) =>
              onChange({ button_radius: event.target.value as Theme['button_radius'] })
            }
          />
          <Select
            label="Font"
            options={FONTS}
            value={theme.font}
            onChange={(event) => onChange({ font: event.target.value as Theme['font'] })}
            className="sm:col-span-2"
          />
        </CardBody>
      </Card>
    </div>
  );
}
