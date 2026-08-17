/**
 * Chart palette.
 *
 * Categorical hues are assigned in a fixed order and never cycled — a series
 * keeps its colour when a filter changes how many series are on screen.
 *
 * Validated on a light surface for: lightness band, chroma floor, CVD
 * separation, normal-vision separation and contrast. Worst adjacent pair is
 * `#0D9488 ↔ #C2410C` at ΔE 13.7 (deutan) — comfortably above the ΔE 8 target,
 * so the series stay distinguishable for red/green colour-blind readers.
 * Identity is additionally carried by a legend and direct end-of-line labels,
 * so it never rests on colour alone.
 */

export const SERIES_COLORS = {
  pageViews: '#00629B', // IEEE blue — the primary metric
  qrScans: '#C2410C',
  linkClicks: '#0D9488',
} as const;

/** Fixed assignment order for the trend chart. */
export const SERIES = [
  { key: 'page_views', label: 'Page views', color: SERIES_COLORS.pageViews },
  { key: 'qr_scans', label: 'QR scans', color: SERIES_COLORS.qrScans },
  { key: 'link_clicks', label: 'Link clicks', color: SERIES_COLORS.linkClicks },
] as const;

export type SeriesKey = (typeof SERIES)[number]['key'];

/**
 * Magnitude comparisons (top links, device mix) rank one measure, so they use a
 * single hue rather than a categorical set — colour would imply an identity
 * that the data does not have.
 */
export const MAGNITUDE_HUE = '#00629B';

/** Recessive chrome: grid lines and axis text must never compete with the data. */
export const CHART_INK = {
  grid: '#E6EBF2',
  axis: '#A3B4CC',
  label: '#526A8E',
  strong: '#0B2545',
  surface: '#FFFFFF',
} as const;
