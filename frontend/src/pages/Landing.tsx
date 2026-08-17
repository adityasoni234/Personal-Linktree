import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  Layers,
  Lock,
  Palette,
  QrCode,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react';

import { LinkButton } from '@/components/ui';
import { useDocumentTitle } from '@/hooks';
import { useIsAuthenticated } from '@/stores/auth';

const FEATURES = [
  {
    icon: Layers,
    title: 'A page for every group',
    body: 'Executive Committee, Computer Society, WIE, SPS, SIGHT, events, workshops — each gets its own branded page at /g/your-name.',
  },
  {
    icon: RefreshCw,
    title: 'QR codes that never expire',
    body: 'The code encodes the group page, not a specific link. Swap what is behind it as often as you like — the printed poster keeps working.',
  },
  {
    icon: Palette,
    title: 'Designed, not generic',
    body: 'Themes, button styles, gradients and a full QR designer with logos, frames and captions — all contrast-checked so they still scan.',
  },
  {
    icon: BarChart3,
    title: 'Analytics without surveillance',
    body: 'Scans, views and per-link clicks. No raw IP addresses stored, no cross-site tracking, no third-party pixels.',
  },
  {
    icon: ShieldCheck,
    title: 'Built for an organization',
    body: 'Roles for admins, editors and members; every sensitive action lands in an audit log you can actually read.',
  },
  {
    icon: Lock,
    title: 'Secure by construction',
    body: 'Argon2id passwords, rotating refresh tokens, strict CSP, rate limiting and sanitised uploads — not bolted on afterwards.',
  },
];

const EXAMPLE_GROUPS = [
  'Executive Committee',
  'Computer Society',
  'WIE',
  'SPS',
  'SIGHT',
  'Events',
  'Workshops',
];

export function LandingPage() {
  useDocumentTitle('');
  const isAuthenticated = useIsAuthenticated();

  return (
    <div className="min-h-screen bg-white">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>

      <header className="sticky top-0 z-30 border-b border-navy-200/70 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ieee-600 text-white">
              <QrCode className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="font-display text-base font-semibold text-navy-900">
              IEEE SOU Link Hub
            </span>
          </Link>

          <nav className="flex items-center gap-2" aria-label="Account">
            {isAuthenticated ? (
              <LinkButton to="/dashboard" rightIcon={<ArrowRight className="h-4 w-4" />}>
                Go to dashboard
              </LinkButton>
            ) : (
              <>
                <LinkButton to="/login" variant="ghost">
                  Sign in
                </LinkButton>
                <LinkButton to="/register">Get started</LinkButton>
              </>
            )}
          </nav>
        </div>
      </header>

      <main id="main">
        {/* ---- Hero ---- */}
        <section className="relative overflow-hidden">
          <div className="surface-grid absolute inset-0 opacity-60" aria-hidden="true" />
          <div
            className="absolute -right-40 top-0 h-[28rem] w-[28rem] rounded-full bg-ieee-100/70 blur-3xl"
            aria-hidden="true"
          />

          <div className="relative mx-auto grid max-w-6xl gap-12 px-5 py-16 sm:px-8 lg:grid-cols-2 lg:items-center lg:py-24">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-ieee-200 bg-ieee-50 px-3 py-1 text-xs font-medium text-ieee-700">
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                Built for IEEE SOU Student Branch
              </span>

              <h1 className="mt-5 font-display text-4xl font-semibold leading-[1.1] tracking-tight text-navy-900 text-balance sm:text-5xl">
                Every chapter. One address.{' '}
                <span className="text-ieee-600">One QR code.</span>
              </h1>

              <p className="mt-5 max-w-xl text-lg leading-relaxed text-navy-600 text-pretty">
                A secure, organization-owned alternative to Linktree. Give each society,
                committee and event its own branded link page — and a QR code you can print
                once and re-point forever.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-3">
                <LinkButton
                  to={isAuthenticated ? '/dashboard' : '/register'}
                  size="lg"
                  rightIcon={<ArrowRight className="h-4 w-4" />}
                >
                  {isAuthenticated ? 'Open dashboard' : 'Create your first group'}
                </LinkButton>
                <LinkButton to="/login" size="lg" variant="outline">
                  Sign in
                </LinkButton>
              </div>

              <dl className="mt-10 grid max-w-md grid-cols-3 gap-6">
                {[
                  { value: '7+', label: 'chapters & committees' },
                  { value: '0', label: 'reprints when links change' },
                  { value: 'AA', label: 'contrast-checked themes' },
                ].map((stat) => (
                  <div key={stat.label}>
                    <dt className="sr-only">{stat.label}</dt>
                    <dd>
                      <span className="block font-display text-2xl font-semibold text-navy-900">
                        {stat.value}
                      </span>
                      <span className="mt-0.5 block text-xs leading-snug text-navy-500">
                        {stat.label}
                      </span>
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* ---- Hierarchy illustration ---- */}
            <div className="relative">
              <div className="rounded-2xl border border-navy-200/70 bg-white p-6 shadow-panel">
                <div className="flex items-center gap-3 border-b border-navy-100 pb-4">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-navy-900 text-white">
                    <Users className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="font-semibold text-navy-900">IEEE SOU</p>
                    <p className="text-xs text-navy-500">Organization</p>
                  </div>
                </div>

                <ul className="mt-4 space-y-2">
                  {EXAMPLE_GROUPS.map((name, index) => (
                    <li
                      key={name}
                      className="flex items-center gap-3 rounded-xl border border-navy-200/70 px-3 py-2.5 transition hover:border-ieee-300 hover:bg-ieee-50/40"
                    >
                      <span className="font-mono text-2xs text-navy-300">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <span className="flex-1 text-sm font-medium text-navy-800">{name}</span>
                      <span className="font-mono text-2xs text-navy-400">
                        /g/{name.toLowerCase().replace(/\s+/g, '-')}
                      </span>
                      <QrCode className="h-4 w-4 text-ieee-500" aria-hidden="true" />
                    </li>
                  ))}
                </ul>
              </div>

              <div className="absolute -bottom-5 -left-5 hidden rounded-xl border border-navy-200/70 bg-white p-3 shadow-panel sm:block">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-success-50 text-success-600">
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-xs font-semibold text-navy-900">Links updated</p>
                    <p className="text-2xs text-navy-500">QR code unchanged</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---- Features ---- */}
        <section className="border-t border-navy-200/70 bg-surface-subtle py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <div className="max-w-2xl">
              <h2 className="font-display text-3xl font-semibold tracking-tight text-navy-900 text-balance">
                Everything a student branch actually needs
              </h2>
              <p className="mt-3 text-navy-600 text-pretty">
                Not a link list with a logo on it — an organization platform with roles,
                analytics and a QR designer that understands error correction.
              </p>
            </div>

            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((feature) => (
                <article
                  key={feature.title}
                  className="rounded-2xl border border-navy-200/70 bg-white p-6 shadow-card transition hover:shadow-card-hover"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ieee-50 text-ieee-600">
                    <feature.icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-4 text-base font-semibold text-navy-900">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-navy-600 text-pretty">
                    {feature.body}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ---- CTA ---- */}
        <section className="py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <div className="relative overflow-hidden rounded-3xl bg-navy-900 px-8 py-12 text-center sm:px-12">
              <div className="surface-grid absolute inset-0 opacity-30" aria-hidden="true" />
              <div className="relative">
                <h2 className="font-display text-3xl font-semibold text-white text-balance">
                  Print the poster once
                </h2>
                <p className="mx-auto mt-3 max-w-xl text-navy-200 text-pretty">
                  Set up a group, add your links, download the QR code. When the registration
                  form changes next semester, change the link — not the poster.
                </p>
                <div className="mt-8 flex flex-wrap justify-center gap-3">
                  <LinkButton
                    to={isAuthenticated ? '/dashboard' : '/register'}
                    size="lg"
                    rightIcon={<ArrowRight className="h-4 w-4" />}
                  >
                    {isAuthenticated ? 'Open dashboard' : 'Get started'}
                  </LinkButton>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-navy-200/70 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 text-sm text-navy-500 sm:px-8">
          <p>© {new Date().getFullYear()} IEEE Silver Oak University Student Branch</p>
          <p className="flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Privacy-conscious analytics · no third-party trackers
          </p>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
