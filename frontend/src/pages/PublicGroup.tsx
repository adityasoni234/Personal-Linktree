import { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Check, Copy, Download, QrCode } from 'lucide-react';

import { ApiError } from '@/api/client';
import { publicApi } from '@/api/endpoints';
import type { PublicGroup as PublicGroupData } from '@/api/types';
import { PublicPageView } from '@/components/public/PublicPageView';
import { backgroundStyle } from '@/lib/theme';
import { Button, Modal, PageLoader } from '@/components/ui';
import { useCopyToClipboard, useQuery } from '@/hooks';

/**
 * Sets the page title and social metadata for a published group.
 *
 * The SPA writes these at runtime; crawlers that do not execute JavaScript are
 * served the same values by the `/public/groups/{slug}/meta` endpoint, which a
 * pre-render or edge worker can consume.
 */
function useSocialMeta(group: PublicGroupData | null) {
  useEffect(() => {
    if (!group) return;

    const title = group.seo?.title || `${group.name} · ${group.organization.name}`;
    const description =
      group.seo?.description ||
      group.description ||
      `All the official links for ${group.name}.`;
    const image = group.seo?.og_image_url || group.logo_url || '';

    const previousTitle = document.title;
    document.title = title;

    const tags: [string, string, string][] = [
      ['name', 'description', description],
      ['property', 'og:title', title],
      ['property', 'og:description', description],
      ['property', 'og:type', 'profile'],
      ['property', 'og:url', group.public_url],
      ['property', 'og:site_name', group.organization.name],
      ['name', 'twitter:card', image ? 'summary_large_image' : 'summary'],
      ['name', 'twitter:title', title],
      ['name', 'twitter:description', description],
    ];
    if (image) {
      tags.push(['property', 'og:image', image], ['name', 'twitter:image', image]);
    }

    const created: HTMLMetaElement[] = [];
    for (const [attribute, key, value] of tags) {
      let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
      if (!element) {
        element = document.createElement('meta');
        element.setAttribute(attribute, key);
        document.head.appendChild(element);
        created.push(element);
      }
      element.setAttribute('content', value);
    }

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement('link');
      canonical.rel = 'canonical';
      document.head.appendChild(canonical);
    }
    canonical.href = group.public_url;

    return () => {
      document.title = previousTitle;
      created.forEach((element) => element.remove());
    };
  }, [group]);
}

export function PublicGroupPage() {
  const { slug = '' } = useParams<{ slug: string }>();
  const [searchParams] = useSearchParams();
  const source = searchParams.get('src') === 'qr' ? 'qr' : 'direct';

  const [qrOpen, setQrOpen] = useState(false);
  const { copied, copy } = useCopyToClipboard();

  const { data, error, isLoading } = useQuery(
    () => publicApi.group(slug, source),
    [slug, source],
    { enabled: Boolean(slug) },
  );

  useSocialMeta(data);

  const share = useCallback(async () => {
    if (!data) return;
    const payload = {
      title: data.name,
      text: data.description ?? `Links for ${data.name}`,
      url: data.public_url,
    };
    // The Web Share sheet is the right affordance on mobile; fall back to the
    // clipboard everywhere else.
    if (navigator.share) {
      try {
        await navigator.share(payload);
        void publicApi.trackShare(slug).catch(() => {});
        return;
      } catch {
        /* the user dismissed the sheet */
      }
    }
    if (await copy(data.public_url)) {
      void publicApi.trackShare(slug).catch(() => {});
    }
  }, [data, slug, copy]);

  if (isLoading) return <PageLoader label="Loading page" />;

  if (error || !data) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-subtle px-6">
        <div className="w-full max-w-md rounded-2xl border border-navy-200/70 bg-white p-8 text-center shadow-card">
          <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-navy-100 text-navy-500">
            <QrCode className="h-6 w-6" aria-hidden="true" />
          </span>
          <h1 className="font-display text-xl font-semibold text-navy-900">
            {notFound ? 'This page is not available' : 'Something went wrong'}
          </h1>
          <p className="mt-2 text-sm text-navy-600 text-pretty">
            {notFound
              ? 'The address may have changed, or the page may not be published yet.'
              : 'Please check your connection and try again.'}
          </p>
          <Link
            to="/"
            className="mt-6 inline-flex items-center justify-center rounded-xl bg-ieee-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-ieee-700"
          >
            Go to IEEE SOU Link Hub
          </Link>
        </div>
      </div>
    );
  }

  const qrPngUrl = publicApi.qrUrl(data.slug, 'png', 1024);

  return (
    <div className="min-h-screen" style={backgroundStyle(data.theme)}>
      <PublicPageView
        name={data.name}
        description={data.description}
        logoUrl={data.logo_url}
        organizationName={data.organization.name}
        theme={data.theme}
        links={data.links}
        hrefFor={(link) => publicApi.linkHref(data.slug, link.id)}
        onShare={() => void share()}
        onShowQr={() => setQrOpen(true)}
      />

      <Modal
        open={qrOpen}
        onClose={() => setQrOpen(false)}
        title={`QR code for ${data.name}`}
        description="Point a camera at this code to open the page."
        size="sm"
        footer={
          <>
            <Button
              variant="ghost"
              leftIcon={copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              onClick={() => void copy(data.public_url)}
            >
              {copied ? 'Copied' : 'Copy link'}
            </Button>
            <a href={qrPngUrl} download={`${data.slug}-qr.png`}>
              <Button leftIcon={<Download className="h-4 w-4" />}>Download PNG</Button>
            </a>
          </>
        }
      >
        <div className="flex flex-col items-center gap-4">
          <img
            src={qrPngUrl}
            alt={`QR code linking to ${data.public_url}`}
            className="h-56 w-56 rounded-xl border border-navy-200 bg-white p-2"
            loading="lazy"
          />
          <p className="break-all text-center font-mono text-2xs text-navy-500">
            {data.public_url}
          </p>
        </div>
      </Modal>
    </div>
  );
}

export default PublicGroupPage;
