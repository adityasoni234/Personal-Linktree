import { FALLBACK_ICON, ICON_REGISTRY } from '@/lib/icons';

/** Renders a link's icon, falling back to a generic link glyph. */
export function LinkIcon({
  name,
  className = 'h-5 w-5',
}: {
  name: string | null | undefined;
  className?: string;
}) {
  const Icon = (name && ICON_REGISTRY[name]) || FALLBACK_ICON;
  return <Icon className={className} aria-hidden="true" />;
}
