/**
 * Renders a group's public page.
 *
 * Shared by the real `/g/:slug` route and the builder's live preview, so what
 * an author sees while editing is literally the same component visitors get.
 *
 * All text is rendered as text nodes — there is no `dangerouslySetInnerHTML`
 * anywhere in this file, or in the app.
 */

import { ExternalLink, QrCode, Share2, Users } from 'lucide-react';

import type { PublicLink, Theme } from '@/api/types';
import { BUTTON_RADIUS, FONT_STACKS, backgroundStyle, withAlpha } from '@/lib/theme';
import { cn } from '@/lib/utils';

import { LinkIcon } from './LinkIcon';

function linkStyle(
  theme: Theme,
  link: Pick<PublicLink, 'style'>,
): { className: string; style: React.CSSProperties } {
  const variant = link.style?.variant ?? 'default';
  const radius = BUTTON_RADIUS[link.style?.border_radius ?? theme.button_radius] ?? BUTTON_RADIUS.lg;
  const background = link.style?.background_color ?? theme.primary_color;
  const text = link.style?.text_color;

  const base: React.CSSProperties = { borderRadius: radius };

  switch (variant === 'default' ? theme.button_style : variant) {
    case 'outline':
      return {
        className: 'border-2 bg-transparent',
        style: { ...base, borderColor: background, color: text ?? background },
      };
    case 'soft':
      return {
        className: 'border border-transparent',
        style: {
          ...base,
          backgroundColor: withAlpha(background, 0.14),
          color: text ?? background,
        },
      };
    case 'glass':
      return {
        className: 'border backdrop-blur-md',
        style: {
          ...base,
          backgroundColor: withAlpha('#FFFFFF', 0.16),
          borderColor: withAlpha('#FFFFFF', 0.28),
          color: text ?? theme.text_color ?? '#FFFFFF',
        },
      };
    case 'minimal':
      return {
        className: 'border-b',
        style: {
          ...base,
          borderRadius: 0,
          borderColor: withAlpha(background, 0.3),
          color: text ?? theme.text_color ?? background,
        },
      };
    case 'featured':
      return {
        className: 'shadow-lg',
        style: {
          ...base,
          backgroundImage: `linear-gradient(135deg, ${background}, ${theme.secondary_color})`,
          color: text ?? '#FFFFFF',
        },
      };
    default:
      return {
        className: 'shadow-sm',
        style: { ...base, backgroundColor: background, color: text ?? '#FFFFFF' },
      };
  }
}

export interface PublicPageViewProps {
  name: string;
  description?: string | null;
  logoUrl?: string | null;
  organizationName?: string;
  theme: Theme;
  links: PublicLink[];
  /** Builds the outbound href; the preview passes a no-op. */
  hrefFor?: (link: PublicLink) => string;
  onShare?: () => void;
  onShowQr?: () => void;
  isPreview?: boolean;
  className?: string;
}

export function PublicPageView({
  name,
  description,
  logoUrl,
  organizationName,
  theme,
  links,
  hrefFor,
  onShare,
  onShowQr,
  isPreview = false,
  className,
}: PublicPageViewProps) {
  const textColor = theme.text_color ?? '#0B1F33';
  const fontFamily = FONT_STACKS[theme.font] ?? FONT_STACKS.inter;
  const activeLinks = links;

  return (
    <div
      className={cn('min-h-full w-full', className)}
      style={{ ...backgroundStyle(theme), color: textColor, fontFamily }}
    >
      <div
        className={cn(
          'mx-auto flex w-full flex-col items-center px-5',
          isPreview ? 'max-w-phone py-8' : 'max-w-md py-12 sm:py-16',
        )}
      >
        {/* ---- Header ---- */}
        <header className="flex w-full flex-col items-center text-center">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={`${name} logo`}
              className={cn(
                'rounded-2xl object-cover shadow-lg ring-1 ring-black/5',
                isPreview ? 'h-16 w-16' : 'h-20 w-20',
              )}
              loading="eager"
            />
          ) : (
            <span
              className={cn(
                'flex items-center justify-center rounded-2xl shadow-lg',
                isPreview ? 'h-16 w-16' : 'h-20 w-20',
              )}
              style={{ backgroundColor: withAlpha(theme.primary_color, 0.16) }}
            >
              <Users
                className={isPreview ? 'h-7 w-7' : 'h-9 w-9'}
                style={{ color: theme.primary_color }}
                aria-hidden="true"
              />
            </span>
          )}

          <h1
            className={cn(
              'mt-4 font-semibold tracking-tight text-balance',
              isPreview ? 'text-lg' : 'text-2xl sm:text-3xl',
            )}
          >
            {name}
          </h1>

          {organizationName && (
            <p
              className={cn('mt-1 font-medium', isPreview ? 'text-2xs' : 'text-sm')}
              style={{ color: withAlpha(textColor, 0.65) }}
            >
              {organizationName}
            </p>
          )}

          {description && (
            <p
              className={cn(
                'mt-3 max-w-sm leading-relaxed text-pretty',
                isPreview ? 'text-xs' : 'text-sm',
              )}
              style={{ color: withAlpha(textColor, 0.8) }}
            >
              {description}
            </p>
          )}
        </header>

        {/* ---- Links ---- */}
        <nav
          className={cn('mt-7 w-full', isPreview ? 'space-y-2' : 'space-y-3')}
          aria-label={`${name} links`}
        >
          {activeLinks.length === 0 ? (
            <p
              className="rounded-xl border border-dashed py-8 text-center text-sm"
              style={{ borderColor: withAlpha(textColor, 0.2), color: withAlpha(textColor, 0.6) }}
            >
              No links yet.
            </p>
          ) : (
            activeLinks.map((link) => {
              const { className: linkClassName, style } = linkStyle(theme, link);
              const content = (
                <>
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center">
                    <LinkIcon
                      name={link.icon}
                      className={isPreview ? 'h-4 w-4' : 'h-5 w-5'}
                    />
                  </span>
                  <span className="min-w-0 flex-1 text-left">
                    <span
                      className={cn(
                        'block truncate font-semibold',
                        isPreview ? 'text-xs' : 'text-sm',
                      )}
                    >
                      {link.title}
                    </span>
                    {link.description && (
                      <span
                        className={cn(
                          'block truncate font-normal opacity-80',
                          isPreview ? 'text-[10px]' : 'text-xs',
                        )}
                      >
                        {link.description}
                      </span>
                    )}
                  </span>
                  <ExternalLink
                    className={cn('shrink-0 opacity-60', isPreview ? 'h-3 w-3' : 'h-4 w-4')}
                    aria-hidden="true"
                  />
                </>
              );

              const shared =
                'flex w-full items-center gap-2.5 transition-transform duration-150 ' +
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ' +
                (isPreview ? 'px-3 py-2.5' : 'px-4 py-3.5 hover:-translate-y-0.5 active:translate-y-0');

              if (isPreview || !hrefFor) {
                return (
                  <div key={link.id} className={cn(shared, linkClassName)} style={style}>
                    {content}
                  </div>
                );
              }

              return (
                <a
                  key={link.id}
                  href={hrefFor(link)}
                  // `noopener` prevents the destination reaching back into this
                  // page; `noreferrer` stops the referrer header leaking.
                  rel="noopener noreferrer nofollow"
                  target="_blank"
                  className={cn(shared, linkClassName)}
                  style={style}
                >
                  {content}
                </a>
              );
            })
          )}
        </nav>

        {/* ---- Actions ---- */}
        {!isPreview && (onShare || onShowQr) && (
          <div className="mt-8 flex items-center gap-2">
            {onShowQr && (
              <button
                type="button"
                onClick={onShowQr}
                className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition"
                style={{
                  backgroundColor: withAlpha(textColor, 0.08),
                  color: textColor,
                }}
              >
                <QrCode className="h-4 w-4" aria-hidden="true" />
                QR code
              </button>
            )}
            {onShare && (
              <button
                type="button"
                onClick={onShare}
                className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition"
                style={{
                  backgroundColor: withAlpha(textColor, 0.08),
                  color: textColor,
                }}
              >
                <Share2 className="h-4 w-4" aria-hidden="true" />
                Share
              </button>
            )}
          </div>
        )}

        <footer
          className={cn('mt-10 text-center', isPreview ? 'text-[10px]' : 'text-2xs')}
          style={{ color: withAlpha(textColor, 0.55) }}
        >
          <p>Powered by IEEE SOU Link Hub</p>
        </footer>
      </div>
    </div>
  );
}
