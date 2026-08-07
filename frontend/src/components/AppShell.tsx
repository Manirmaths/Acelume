import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import Logo from './ui/Logo';

interface NavItem {
  to: string;
  labelKey: string;
  icon: string;
  /**
   * Routes that live UNDER this destination. Used so that, say, /blitz still
   * highlights "Practice" -- otherwise a student who navigates two levels in
   * sees no tab selected and loses their sense of place.
   */
  owns?: string[];
}

/**
 * Primary navigation: five destinations, no more.
 *
 * This replaced a fourteen-item sidebar. Fourteen equally-weighted choices is
 * not a menu, it is a search problem, and six of those items were engagement
 * features (leaderboard, league, battles, blitz, achievements, planner)
 * competing for attention with the student's actual learning work. Everything
 * that was removed is still reachable in two taps via the Practice, Progress
 * and Profile hubs -- nothing was deleted, only de-promoted.
 *
 * The rule going forward: a feature does not enter primary navigation because
 * it is new. It enters through the surface where it is relevant. If a feature
 * can only be found via nav, it is not integrated yet.
 *
 * See PRODUCT-ARCHITECTURE.md §5.
 */
const NAV_ITEMS: NavItem[] = [
  {
    to: '/dashboard',
    labelKey: 'nav.home',
    icon: 'fa-solid fa-house',
  },
  {
    to: '/learn',
    labelKey: 'nav.learn',
    icon: 'fa-solid fa-graduation-cap',
    owns: ['/subjects'],
  },
  {
    to: '/practice',
    labelKey: 'nav.practice',
    icon: 'fa-solid fa-pen-to-square',
    owns: ['/quiz', '/quiz-attempt', '/mock', '/mock-attempt', '/blitz', '/rush', '/battles', '/review', '/flashcards', '/results'],
  },
  {
    to: '/progress',
    labelKey: 'nav.progress',
    icon: 'fa-solid fa-chart-line',
    owns: ['/achievements', '/league', '/leaderboard', '/study-planner'],
  },
  {
    to: '/profile',
    labelKey: 'nav.profile',
    icon: 'fa-solid fa-user',
    owns: ['/family', '/admin'],
  },
];

function isOwned(item: NavItem, pathname: string): boolean {
  if (pathname === item.to || pathname.startsWith(`${item.to}/`)) return true;
  return (item.owns || []).some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export default function AppShell() {
  const { user } = useAuth();
  const { t } = useLanguage();
  // From the router, not window.location: this must re-evaluate on every
  // client-side navigation, and reading window directly would leave a stale
  // tab highlighted after a route change that doesn't remount the shell.
  const { pathname } = useLocation();

  if (!user) return null;

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <Link to="/dashboard" className="flex items-center gap-2 font-display font-extrabold text-lg text-ink-900 px-5 py-5">
        <Logo className="w-8 h-8 rounded-xl shadow-sm" />
        Acelume
      </Link>

      <nav className="flex-1 px-3 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                isActive || isOwned(item, pathname)
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
              }`
            }
          >
            <i className={`${item.icon} w-4 text-center`} />
            {t(item.labelKey)}
          </NavLink>
        ))}
      </nav>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-ink-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-white focus:text-ink-900 focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-pop focus:font-semibold"
      >
        Skip to main content
      </a>

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-64 border-r border-ink-100 bg-white flex-shrink-0">
        {sidebarContent}
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-ink-100 h-16 flex items-center justify-between px-4 sm:px-6">
          {/* On mobile the bottom bar is the navigation, so the top bar carries
              identity rather than a hamburger that opens a duplicate menu. */}
          <Link to="/dashboard" className="lg:hidden flex items-center gap-2 font-display font-extrabold text-ink-900">
            <Logo className="w-8 h-8 rounded-xl shadow-sm" />
            Acelume
          </Link>
          <div className="hidden lg:block" />

          <div className="flex items-center gap-3">
            {user.streak_freezes > 0 && (
              <div
                className="flex items-center gap-1.5 rounded-full bg-info-50 text-info-500 px-3 py-1.5 text-sm font-bold"
                title={`${user.streak_freezes} streak freeze${user.streak_freezes === 1 ? '' : 's'} -- auto-protects a missed day`}
              >
                <i className="fa-solid fa-snowflake" />
                {user.streak_freezes}
              </div>
            )}
            <div className="flex items-center gap-1.5 rounded-full bg-flame-500/10 text-flame-500 px-3 py-1.5 text-sm font-bold">
              <i className="fa-solid fa-fire" />
              {user.current_streak}
            </div>
            <div className="flex items-center gap-1.5 rounded-full bg-brand-50 text-brand-700 px-3 py-1.5 text-sm font-bold">
              <i className="fa-solid fa-star" />
              {user.points}
            </div>
          </div>
        </header>

        {/* pb-20 on mobile keeps the last element clear of the bottom bar. */}
        <main id="main-content" className="flex-1 min-w-0 pb-20 lg:pb-0">
          <Outlet />
        </main>
      </div>

      {/*
        Mobile bottom tab bar.

        This replaced a hamburger drawer. A drawer is the right pattern for a
        long list and the wrong one for five items: it hides the whole of the
        app behind a tap, gives no sense of where you are, and puts every
        destination the same distance away. Thumb-reachable tabs are also
        simply better on the phones this app actually runs on.
      */}
      <nav
        className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t border-ink-100 flex"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
        aria-label="Primary"
      >
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-semibold transition-colors ${
                isActive || isOwned(item, pathname) ? 'text-brand-600' : 'text-ink-400'
              }`
            }
          >
            <i className={`${item.icon} text-base`} aria-hidden="true" />
            {t(item.labelKey)}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
