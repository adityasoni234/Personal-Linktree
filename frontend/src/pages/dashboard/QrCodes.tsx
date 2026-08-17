import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Copy, Download, Palette, QrCode } from 'lucide-react';

import { groupsApi, publicApi, qrApi } from '@/api/endpoints';
import type { GroupSummary } from '@/api/types';
import { PageHeader } from '@/components/layout/DashboardLayout';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LinkButton,
  SkeletonCard,
} from '@/components/ui';
import { useCopyToClipboard, useDocumentTitle, useQuery } from '@/hooks';
import { downloadBlob } from '@/lib/utils';
import { toast } from '@/stores/toast';

function QrCard({ group }: { group: GroupSummary }) {
  const { copied, copy } = useCopyToClipboard();
  const [downloading, setDownloading] = useState<'png' | 'svg' | null>(null);

  const handleDownload = async (format: 'png' | 'svg') => {
    setDownloading(format);
    try {
      const blob = await qrApi.download(group.id, format, 1024);
      downloadBlob(blob, `${group.slug}-qr.${format}`);
      toast.success(`${format.toUpperCase()} downloaded`);
    } catch {
      toast.error('Download failed', 'Please try again in a moment.');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Card interactive className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/dashboard/groups/${group.id}`}
            className="block truncate font-semibold text-navy-900 hover:text-ieee-700"
          >
            {group.name}
          </Link>
          <p className="truncate font-mono text-2xs text-navy-400">/g/{group.slug}</p>
        </div>
        <Badge tone={group.is_published ? 'success' : 'warning'} dot size="sm">
          {group.is_published ? 'Live' : 'Draft'}
        </Badge>
      </div>

      <div className="mt-4 flex items-center justify-center rounded-xl border border-navy-200 bg-white p-3">
        {/* The public QR endpoint only serves published groups, so a draft shows
            a placeholder rather than a broken image. */}
        {group.is_published ? (
          <img
            src={publicApi.qrUrl(group.slug, 'png', 512)}
            alt={`QR code for ${group.name}`}
            className="h-40 w-40 object-contain"
            loading="lazy"
          />
        ) : (
          <div className="flex h-40 w-40 flex-col items-center justify-center gap-2 rounded-lg bg-surface-subtle text-center">
            <QrCode className="h-8 w-8 text-navy-300" aria-hidden="true" />
            <p className="px-3 text-2xs text-navy-500">
              Publish the group to share its code
            </p>
          </div>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <Button
          variant="outline"
          size="sm"
          isLoading={downloading === 'png'}
          leftIcon={<Download className="h-4 w-4" />}
          onClick={() => void handleDownload('png')}
        >
          PNG
        </Button>
        <Button
          variant="outline"
          size="sm"
          isLoading={downloading === 'svg'}
          leftIcon={<Download className="h-4 w-4" />}
          onClick={() => void handleDownload('svg')}
        >
          SVG
        </Button>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          onClick={() => {
            void copy(group.public_url).then((ok) =>
              ok ? toast.success('Link copied') : toast.error('Could not copy'),
            );
          }}
        >
          {copied ? 'Copied' : 'Copy link'}
        </Button>
        <LinkButton
          to={`/dashboard/groups/${group.id}`}
          variant="ghost"
          size="sm"
          leftIcon={<Palette className="h-4 w-4" />}
        >
          Design
        </LinkButton>
      </div>
    </Card>
  );
}

export function QrCodesPage() {
  useDocumentTitle('QR codes');
  const { data, error, isLoading, refetch } = useQuery(
    () => groupsApi.list({ limit: 60, sort: 'position' }),
    [],
  );

  return (
    <>
      <PageHeader
        title="QR codes"
        description="One dynamic code per group. Printing it once is enough — the links behind it stay editable."
      />

      {error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : (data?.data.length ?? 0) === 0 ? (
        <EmptyState
          icon={<QrCode className="h-6 w-6" aria-hidden="true" />}
          title="No QR codes yet"
          description="Every group gets a QR code automatically. Create a group to generate your first one."
          action={<LinkButton to="/dashboard/groups/new">Create a group</LinkButton>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data?.data.map((group) => (
            <QrCard key={group.id} group={group} />
          ))}
        </div>
      )}
    </>
  );
}

export default QrCodesPage;
