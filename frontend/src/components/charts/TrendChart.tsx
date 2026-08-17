import { useId, useMemo, useState } from 'react';
import { Table2, TrendingUp } from 'lucide-react';

import type { MetricPoint } from '@/api/types';
import { CHART_INK, SERIES } from '@/lib/chartColors';
import { cn, formatNumber } from '@/lib/utils';

interface TrendChartProps {
  data: MetricPoint[];
  height?: number;
  className?: string;
  title?: string;
}

const VIEW_WIDTH = 760;
const PADDING = { top: 16, right: 92, bottom: 28, left: 44 };

function niceCeiling(value: number): number {
  if (value <= 5) return 5;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / magnitude) * magnitude;
}

function formatAxisDate(iso: string): string {
  const date = new Date(iso);
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(date);
}

/**
 * Multi-series trend line.
 *
 * One shared y-axis for all three series — they are all counts of the same
 * kind of thing, so a second scale would invent a relationship that is not in
 * the data.
 */
export function TrendChart({ data, height = 280, className, title }: TrendChartProps) {
  const clipId = useId();
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  const chart = useMemo(() => {
    const points = data.length > 0 ? data : [];
    const maxValue = points.reduce(
      (max, point) =>
        Math.max(max, point.page_views, point.qr_scans, point.link_clicks),
      0,
    );
    const yMax = niceCeiling(Math.max(maxValue, 1));

    const innerWidth = VIEW_WIDTH - PADDING.left - PADDING.right;
    const innerHeight = height - PADDING.top - PADDING.bottom;
    const step = points.length > 1 ? innerWidth / (points.length - 1) : 0;

    const x = (index: number) =>
      points.length > 1 ? PADDING.left + index * step : PADDING.left + innerWidth / 2;
    const y = (value: number) => PADDING.top + innerHeight - (value / yMax) * innerHeight;

    const paths = SERIES.map((series) => ({
      ...series,
      d: points
        .map((point, index) => `${index === 0 ? 'M' : 'L'}${x(index)},${y(point[series.key])}`)
        .join(' '),
      last: points.length > 0 ? points[points.length - 1]![series.key] : 0,
      total: points.reduce((sum, point) => sum + point[series.key], 0),
    }));

    // Four gridlines is enough to read a value; more is chart junk.
    const ticks = Array.from({ length: 5 }, (_, index) => (yMax / 4) * index);

    // Thin x labels so they never collide on a narrow viewport.
    const labelStride = Math.max(1, Math.ceil(points.length / 7));

    return { points, yMax, x, y, paths, ticks, innerHeight, labelStride };
  }, [data, height]);

  const hasData = chart.paths.some((series) => series.total > 0);
  const active = hoverIndex !== null ? chart.points[hoverIndex] : null;

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    if (chart.points.length === 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = ((event.clientX - rect.left) / rect.width) * VIEW_WIDTH;
    const innerWidth = VIEW_WIDTH - PADDING.left - PADDING.right;
    const relative = (ratio - PADDING.left) / innerWidth;
    const index = Math.round(relative * (chart.points.length - 1));
    setHoverIndex(Math.min(chart.points.length - 1, Math.max(0, index)));
  };

  if (showTable) {
    return (
      <div className={className}>
        <div className="mb-3 flex items-center justify-between">
          {title && <h3 className="text-sm font-semibold text-navy-900">{title}</h3>}
          <button
            type="button"
            onClick={() => setShowTable(false)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-navy-600 hover:bg-navy-100"
          >
            <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
            View chart
          </button>
        </div>
        <div className="scroll-x max-h-80">
          <table className="w-full text-sm">
            <caption className="sr-only">Traffic over time, as a table</caption>
            <thead className="sticky top-0 bg-white">
              <tr className="border-b border-navy-200 text-left text-xs text-navy-500">
                <th scope="col" className="py-2 pr-4 font-medium">Date</th>
                {SERIES.map((series) => (
                  <th key={series.key} scope="col" className="py-2 pr-4 text-right font-medium">
                    {series.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {chart.points.map((point) => (
                <tr key={point.date} className="border-b border-navy-100 last:border-0">
                  <th scope="row" className="py-1.5 pr-4 text-left font-normal text-navy-700">
                    {formatAxisDate(point.date)}
                  </th>
                  {SERIES.map((series) => (
                    <td
                      key={series.key}
                      className="py-1.5 pr-4 text-right tabular-nums text-navy-800"
                    >
                      {point[series.key].toLocaleString('en-IN')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        {title && <h3 className="text-sm font-semibold text-navy-900">{title}</h3>}
        <div className="flex items-center gap-4">
          {/* A legend is always present for multiple series, so identity never
              depends on colour alone. */}
          <ul className="flex flex-wrap items-center gap-3">
            {SERIES.map((series) => (
              <li key={series.key} className="flex items-center gap-1.5 text-xs text-navy-600">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: series.color }}
                  aria-hidden="true"
                />
                {series.label}
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setShowTable(true)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-navy-600 hover:bg-navy-100"
          >
            <Table2 className="h-3.5 w-3.5" aria-hidden="true" />
            View as table
          </button>
        </div>
      </div>

      {!hasData ? (
        <div
          className="flex items-center justify-center rounded-xl border border-dashed border-navy-200 bg-surface-subtle/60 text-sm text-navy-500"
          style={{ height }}
        >
          No traffic recorded in this period yet.
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${VIEW_WIDTH} ${height}`}
            className="w-full touch-none"
            style={{ height }}
            role="img"
            aria-label={`Traffic trend. ${chart.paths
              .map((series) => `${series.label}: ${series.total} total`)
              .join('. ')}`}
            onPointerMove={handlePointerMove}
            onPointerLeave={() => setHoverIndex(null)}
          >
            <defs>
              <clipPath id={clipId}>
                <rect
                  x={PADDING.left}
                  y={PADDING.top - 4}
                  width={VIEW_WIDTH - PADDING.left - PADDING.right}
                  height={chart.innerHeight + 8}
                />
              </clipPath>
            </defs>

            {/* Recessive grid */}
            {chart.ticks.map((tick) => (
              <g key={tick}>
                <line
                  x1={PADDING.left}
                  x2={VIEW_WIDTH - PADDING.right}
                  y1={chart.y(tick)}
                  y2={chart.y(tick)}
                  stroke={CHART_INK.grid}
                  strokeWidth={1}
                />
                <text
                  x={PADDING.left - 10}
                  y={chart.y(tick)}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontSize={11}
                  fill={CHART_INK.label}
                >
                  {formatNumber(Math.round(tick))}
                </text>
              </g>
            ))}

            {/* X labels */}
            {chart.points.map((point, index) =>
              index % chart.labelStride === 0 || index === chart.points.length - 1 ? (
                <text
                  key={point.date}
                  x={chart.x(index)}
                  y={height - 8}
                  textAnchor="middle"
                  fontSize={11}
                  fill={CHART_INK.label}
                >
                  {formatAxisDate(point.date)}
                </text>
              ) : null,
            )}

            {/* Crosshair */}
            {hoverIndex !== null && (
              <line
                x1={chart.x(hoverIndex)}
                x2={chart.x(hoverIndex)}
                y1={PADDING.top}
                y2={PADDING.top + chart.innerHeight}
                stroke={CHART_INK.axis}
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            )}

            <g clipPath={`url(#${clipId})`}>
              {chart.paths.map((series) => (
                <path
                  key={series.key}
                  d={series.d}
                  fill="none"
                  stroke={series.color}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ))}
            </g>

            {/* Hover markers, with a surface ring so overlapping points stay
                readable. */}
            {hoverIndex !== null &&
              active &&
              chart.paths.map((series) => (
                <circle
                  key={series.key}
                  cx={chart.x(hoverIndex)}
                  cy={chart.y(active[series.key])}
                  r={4.5}
                  fill={series.color}
                  stroke={CHART_INK.surface}
                  strokeWidth={2}
                />
              ))}

            {/* Direct end-of-line labels — three series, so each is labelled. */}
            {chart.paths.map((series) => (
              <text
                key={`label-${series.key}`}
                x={VIEW_WIDTH - PADDING.right + 10}
                y={chart.y(series.last)}
                dominantBaseline="middle"
                fontSize={11}
                fontWeight={600}
                fill={CHART_INK.label}
              >
                {formatNumber(series.last)}
              </text>
            ))}
          </svg>

          {hoverIndex !== null && active && (
            <div
              className="pointer-events-none absolute top-2 z-10 min-w-[9rem] rounded-xl border border-navy-200/70 bg-white p-2.5 shadow-panel"
              style={{
                left: `calc(${(chart.x(hoverIndex) / VIEW_WIDTH) * 100}% + 8px)`,
                transform:
                  chart.x(hoverIndex) > VIEW_WIDTH * 0.65
                    ? 'translateX(calc(-100% - 16px))'
                    : undefined,
              }}
            >
              <p className="text-2xs font-semibold uppercase tracking-wide text-navy-400">
                {formatAxisDate(active.date)}
              </p>
              <ul className="mt-1.5 space-y-1">
                {SERIES.map((series) => (
                  <li
                    key={series.key}
                    className="flex items-center justify-between gap-4 text-xs"
                  >
                    <span className="flex items-center gap-1.5 text-navy-600">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: series.color }}
                        aria-hidden="true"
                      />
                      {series.label}
                    </span>
                    <span className="font-semibold tabular-nums text-navy-900">
                      {active[series.key].toLocaleString('en-IN')}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Horizontal magnitude bars                                                  */
/* -------------------------------------------------------------------------- */

interface BarBreakdownProps {
  items: { id?: string | null; label: string; count: number; share?: number }[];
  emptyMessage?: string;
  valueLabel?: string;
  className?: string;
  max?: number;
}

/**
 * Ranked magnitude for a single measure, so every bar shares one hue — a
 * categorical palette here would imply an identity the data does not carry.
 */
export function BarBreakdown({
  items,
  emptyMessage = 'Nothing recorded yet.',
  valueLabel = 'clicks',
  className,
  max,
}: BarBreakdownProps) {
  const ceiling = max ?? Math.max(1, ...items.map((item) => item.count));

  if (items.length === 0) {
    return <p className={cn('py-6 text-center text-sm text-navy-500', className)}>{emptyMessage}</p>;
  }

  return (
    <ul className={cn('space-y-3', className)}>
      {items.map((item, index) => (
        <li key={item.id ?? `${item.label}-${index}`} className="group">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate text-navy-700" title={item.label}>
              {item.label}
            </span>
            <span className="shrink-0 font-semibold tabular-nums text-navy-900">
              {item.count.toLocaleString('en-IN')}
              {item.share !== undefined && (
                <span className="ml-1.5 text-xs font-normal text-navy-400">
                  {item.share}%
                </span>
              )}
            </span>
          </div>
          <div
            className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-navy-100"
            role="img"
            aria-label={`${item.label}: ${item.count} ${valueLabel}`}
          >
            <div
              className="h-full rounded-full bg-ieee-600 transition-[width] duration-500"
              style={{ width: `${Math.max(2, (item.count / ceiling) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
