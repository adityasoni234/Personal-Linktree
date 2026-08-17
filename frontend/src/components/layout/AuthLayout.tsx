import { Link } from 'react-router-dom';
import { QrCode, ShieldCheck, BarChart3, Layers } from 'lucide-react';

const HIGHLIGHTS = [
  {
    icon: <QrCode className="h-4 w-4" aria-hidden="true" />,
    title: 'QR codes that never go stale',
    body: 'The code points at your page, so you can change every link behind it without reprinting a thing.',
  },
  {
    icon: <Layers className="h-4 w-4" aria-hidden="true" />,
    title: 'One hub per chapter',
    body: 'Computer Society, WIE, SIGHT, SPS, events, workshops — each with its own branded page.',
  },
  {
    icon: <BarChart3 className="h-4 w-4" aria-hidden="true" />,
    title: 'Know what works',
    body: 'Scans, views and clicks per link — measured without tracking your visitors around the web.',
  },
];

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_minmax(0,32rem)]">
      {/* Brand panel — hidden on small screens where it would just push the
          form below the fold. */}
      <aside className="relative hidden overflow-hidden bg-navy-900 px-12 py-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="surface-grid absolute inset-0 opacity-[0.35]" aria-hidden="true" />
        <div
          className="absolute -left-24 top-1/3 h-96 w-96 rounded-full bg-ieee-600/30 blur-3xl"
          aria-hidden="true"
        />

        <div className="relative">
          <Link to="/" className="inline-flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ieee-600">
              <QrCode className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="font-display text-lg font-semibold">IEEE SOU Link Hub</span>
          </Link>
        </div>

        <div className="relative max-w-md">
          <h2 className="font-display text-3xl font-semibold leading-tight text-balance">
            Every chapter. One address. One QR code.
          </h2>
          <ul className="mt-8 space-y-5">
            {HIGHLIGHTS.map((item) => (
              <li key={item.title} className="flex gap-3">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-ieee-200">
                  {item.icon}
                </span>
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-navy-200">{item.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative flex items-center gap-2 text-sm text-navy-300">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          Argon2id passwords, rotating sessions, full audit trail.
        </p>
      </aside>

      <main className="flex items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-8 inline-flex items-center gap-2.5 lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ieee-600 text-white">
              <QrCode className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="font-display text-lg font-semibold text-navy-900">
              IEEE SOU Link Hub
            </span>
          </Link>

          <h1 className="font-display text-2xl font-semibold text-navy-900">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-navy-500 text-pretty">{subtitle}</p>}

          <div className="mt-7">{children}</div>

          {footer && <div className="mt-6 text-sm text-navy-500">{footer}</div>}
        </div>
      </main>
    </div>
  );
}
