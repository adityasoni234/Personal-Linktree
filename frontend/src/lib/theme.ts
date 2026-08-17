/**
 * Theme helpers shared by the public page and the builder preview.
 *
 * Kept out of the component file so that module exports a component and nothing
 * else, which is what keeps fast refresh working.
 */

import type { Theme } from '@/api/types';

export const BUTTON_RADIUS: Record<string, string> = {
  none: '0px',
  sm: '6px',
  md: '10px',
  lg: '14px',
  full: '9999px',
};

export const FONT_STACKS: Record<string, string> = {
  inter: "'Inter', ui-sans-serif, system-ui, sans-serif",
  'dm-sans': "'DM Sans', 'Inter', ui-sans-serif, system-ui, sans-serif",
  'space-grotesk': "'Space Grotesk', 'Inter', ui-sans-serif, system-ui, sans-serif",
  'source-serif': "'Source Serif 4', Georgia, ui-serif, serif",
  system: 'ui-sans-serif, system-ui, -apple-system, sans-serif',
};

/** `#RRGGBB` + alpha → `rgba()`, for soft/glass button fills. */
export function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace('#', '');
  if (value.length < 6) return hex;
  const red = parseInt(value.slice(0, 2), 16);
  const green = parseInt(value.slice(2, 4), 16);
  const blue = parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

export function backgroundStyle(theme: Theme): React.CSSProperties {
  if (theme.background_style === 'gradient') {
    return {
      backgroundImage: `linear-gradient(160deg, ${theme.background_color} 0%, ${
        theme.background_end_color ?? theme.primary_color
      } 100%)`,
    };
  }
  if (theme.background_style === 'pattern') {
    return {
      backgroundColor: theme.background_color,
      backgroundImage: `radial-gradient(${withAlpha(theme.primary_color, 0.12)} 1px, transparent 1px)`,
      backgroundSize: '18px 18px',
    };
  }
  return { backgroundColor: theme.background_color };
}
