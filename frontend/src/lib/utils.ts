/** Small shared helpers. */

/**
 * Conditional className joiner — a tiny `clsx` so we do not add a dependency.
 * Non-string values (including the `0` that `&&` can produce) are dropped.
 */
export function cn(...values: unknown[]): string {
  return values.filter((value): value is string => typeof value === 'string' && value !== '').join(' ');
}

export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return '0';
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 10_000) return `${(value / 1000).toFixed(1)}k`;
  return new Intl.NumberFormat('en-IN').format(value);
}

export function formatDate(value: string | Date, style: 'short' | 'long' = 'short'): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: style === 'long' ? 'long' : 'short',
    year: 'numeric',
    ...(style === 'long' ? { hour: '2-digit', minute: '2-digit' } : {}),
  }).format(date);
}

export function formatRelativeTime(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '—';

  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['week', 604_800],
    ['day', 86_400],
    ['hour', 3600],
    ['minute', 60],
  ];
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

  for (const [unit, secondsPerUnit] of units) {
    if (Math.abs(seconds) >= secondsPerUnit) {
      return formatter.format(Math.round(seconds / secondsPerUnit), unit);
    }
  }
  return 'just now';
}

export function slugify(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-')
    .slice(0, 48);
}

export function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Percentage change between two periods, guarding against divide-by-zero. */
export function percentChange(current: number, previous: number): number | null {
  if (previous === 0) return current === 0 ? 0 : null;
  return Math.round(((current - previous) / previous) * 100);
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoke on the next tick so the download has started.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Display form of a URL: strips the scheme and trailing slash, and truncates.
 * Purely cosmetic — the real href always uses the stored, validated URL.
 */
export function prettyUrl(url: string, maxLength = 42): string {
  const stripped = url.replace(/^https?:\/\//, '').replace(/\/$/, '');
  return stripped.length > maxLength ? `${stripped.slice(0, maxLength - 1)}…` : stripped;
}

export const ROLE_LABELS: Record<string, string> = {
  SUPER_ADMIN: 'Super admin',
  ADMIN: 'Administrator',
  EDITOR: 'Editor',
  USER: 'Member',
};

export const ROLE_DESCRIPTIONS: Record<string, string> = {
  SUPER_ADMIN: 'Full access across every organization on the platform.',
  ADMIN: 'Manages this organization: groups, members, roles and the audit log.',
  EDITOR: 'Creates and edits groups and links across the organization.',
  USER: 'Creates and manages their own groups.',
};
