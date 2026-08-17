import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  ClipboardList,
  LayoutDashboard,
  Link2,
  LogOut,
  Menu as MenuIcon,
  Plus,
  QrCode,
  Settings,
  Shield,
  User as UserIcon,
  Users,
  X,
} from 'lucide-react';

import type { Role } from '@/api/types';
import { Button, LinkButton, Menu } from '@/components/ui';
import { useDismissable } from '@/hooks';
import { cn, initials } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { toast } from '@/stores/toast';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  roles?: Role[];
  end?: boolean;
}

const PRIMARY_NAV: NavItem[] = [
  { to: '/dashboard', label: 'Overview', icon: <LayoutDashboard className="h-4 w-4" />, end: true },
  { to: '/dashboard/groups', label: 'Groups', icon: <Users className="h-4 w-4" /> },
  { to: '/dashboard/links', label: 'Links', icon: <Link2 className="h-4 w-4" /> },
  { to: '/dashboard/qr-codes', label: 'QR codes', icon: <QrCode className="h-4 w-4" /> },
  { to: '/dashboard/analytics', label: 'Analytics', icon: <BarChart3 className="h-4 w-4" /> },
];

const ADMIN_NAV: NavItem[] = [
  {
    to: '/admin/users',
    label: 'Members',
    icon: <Users className="h-4 w-4" />,
    roles: ['ADMIN', 'SUPER_ADMIN'],
  },
  {
    to: '/admin/audit-logs',
    label: 'Audit log',
    icon: <ClipboardList className="h-4 w-4" />,
    roles: ['ADMIN', 'SUPER_ADMIN'],
  },
  {
    to: '/admin/system',
    label: 'System',
    icon: <Shield className="h-4 w-4" />,
    roles: ['SUPER_ADMIN'],
  },
];

const ACCOUNT_NAV: NavItem[] = [
  { to: '/dashboard/profile', label: 'Profile', icon: <UserIcon className="h-4 w-4" /> },
  { to: '/dashboard/settings', label: 'Settings', icon: <Settings className="h-4 w-4" /> },
];

function NavSection({
  title,
  items,
  role,
  onNavigate,
}: {
  title?: string;
  items: NavItem[];
  role: Role | undefined;
  onNavigate?: () => void;
}) {
  const visible = items.filter((item) => !item.roles || (role && item.roles.includes(role)));
  if (visible.length === 0) return null;

  return (
    <div className="space-y-1">
      {title && (
        <p className="px-3 pb-1 pt-4 text-2xs font-semibold uppercase tracking-wider text-navy-400">
          {title}
        </p>
      )}
      {visible.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition',
              isActive
                ? 'bg-ieee-50 text-ieee-700'
                : 'text-navy-600 hover:bg-navy-100 hover:text-navy-900',
            )
          }
        >
          {({ isActive }) => (
            <>
              <span className={cn(isActive ? 'text-ieee-600' : 'text-navy-400')}>
                {item.icon}
              </span>
              {item.label}
            </>
          )}
        </NavLink>
      ))}
    </div>
  );
}

export function DashboardLayout() {
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const sidebarRef = useDismissable<HTMLDivElement>(mobileOpen, () => setMobileOpen(false));

  // Close the drawer whenever the route changes, otherwise it lingers over the
  // new page on mobile.
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleSignOut = async () => {
    await signOut();
    toast.success('Signed out', 'You have been signed out of this device.');
    navigate('/login', { replace: true });
  };

  const sidebar = (
    <>
      <Link to="/dashboard" className="flex items-center gap-2.5 px-3 py-1">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ieee-600 text-white">
          <QrCode className="h-5 w-5" aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block truncate font-display text-sm font-semibold text-navy-900">
            IEEE SOU Link Hub
          </span>
          <span className="block truncate text-2xs text-navy-400">
            {user?.organization_name ?? 'Organization'}
          </span>
        </span>
      </Link>

      <div className="mt-5 px-3">
        <LinkButton to="/dashboard/groups/new" fullWidth leftIcon={<Plus className="h-4 w-4" />}>
          New group
        </LinkButton>
      </div>

      <nav className="mt-5 flex-1 space-y-1 overflow-y-auto px-3 pb-4" aria-label="Main">
        <NavSection items={PRIMARY_NAV} role={user?.effective_role} />
        <NavSection title="Administration" items={ADMIN_NAV} role={user?.effective_role} />
        <NavSection title="Account" items={ACCOUNT_NAV} role={user?.effective_role} />
      </nav>

      <div className="border-t border-navy-200/70 p-3">
        <div className="flex items-center gap-3 rounded-xl px-2 py-2">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-navy-900 text-xs font-semibold text-white">
            {user ? initials(user.full_name) : '—'}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-navy-900">{user?.full_name}</p>
            <p className="truncate text-2xs text-navy-400">{user?.email}</p>
          </div>
          <Menu
            label="Account menu"
            items={[
              {
                label: 'Profile',
                icon: <UserIcon className="h-4 w-4" />,
                onSelect: () => navigate('/dashboard/profile'),
              },
              {
                label: 'Settings',
                icon: <Settings className="h-4 w-4" />,
                onSelect: () => navigate('/dashboard/settings'),
              },
              {
                label: 'Sign out',
                icon: <LogOut className="h-4 w-4" />,
                tone: 'danger',
                separated: true,
                onSelect: () => void handleSignOut(),
              },
            ]}
          />
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-surface-subtle">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-68 flex-col border-r border-navy-200/70 bg-white lg:flex">
        <div className="flex h-full flex-col py-4">{sidebar}</div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-navy-900/40 backdrop-blur-[2px]" aria-hidden="true" />
          <div
            ref={sidebarRef}
            className="relative flex h-full w-72 max-w-[85vw] animate-slide-in-right flex-col bg-white py-4 shadow-panel"
          >
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
              className="absolute right-3 top-3 rounded-lg p-1.5 text-navy-400 hover:bg-navy-100"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
            {sidebar}
          </div>
        </div>
      )}

      <div className="lg:pl-68">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-navy-200/70 bg-white/85 px-4 backdrop-blur sm:px-6 lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon className="h-5 w-5" aria-hidden="true" />
          </Button>
          <Link to="/dashboard" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ieee-600 text-white">
              <QrCode className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="font-display text-sm font-semibold">Link Hub</span>
          </Link>
        </header>

        <main id="main-content" className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  breadcrumb?: React.ReactNode;
}

export function PageHeader({ title, description, actions, breadcrumb }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {breadcrumb && <div className="mb-1.5">{breadcrumb}</div>}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-navy-900">
          {title}
        </h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-navy-500 text-pretty">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
