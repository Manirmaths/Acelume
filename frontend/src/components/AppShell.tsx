import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import Avatar from './ui/Avatar';
import LanguageSwitcher from './ui/LanguageSwitcher';
import { disablePush, enablePush, getPushState, type PushSupport } from '../lib/push';

interface NavItem {
  to: string;
  labelKey: string;
  icon: string;
  adminOnly?: boolean;
}

// labelKey looks up i18n/translations.ts -- see LanguageContext's t().
const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', labelKey: 'nav.dashboard', icon: 'fa-solid fa-gauge-high' },
  { to: '/subjects', labelKey: 'nav.subjects', icon: 'fa-solid fa-book-open' },
  { to: '/learn', labelKey: 'nav.learn', icon: 'fa-solid fa-graduation-cap' },
  { to: '/leaderboard', labelKey: 'nav.leaderboard', icon: 'fa-solid fa-ranking-star' },
  { to: '/blitz', labelKey: 'nav.blitz', icon: 'fa-solid fa-bolt' },
  { to: '/mock', labelKey: 'nav.mock', icon: 'fa-solid fa-file-signature' },
  { to: '/study-planner', labelKey: 'nav.studyPlanner', icon: 'fa-solid fa-calendar-days' },
  { to: '/flashcards', labelKey: 'nav.flashcards', icon: 'fa-solid fa-layer-group' },
  { to: '/achievements', labelKey: 'nav.achievements', icon: 'fa-solid fa-medal' },
  { to: '/review', labelKey: 'nav.review', icon: 'fa-solid fa-bookmark' },
  { to: '/family', labelKey: 'nav.family', icon: 'fa-solid fa-people-roof' },
  { to: '/admin', labelKey: 'nav.admin', icon: 'fa-solid fa-user-shield', adminOnly: true },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [pushState, setPushState] = useState<PushSupport>('unsupported');
  const [pushBusy, setPushBusy] = useState(false);

  useEffect(() => {
    getPushState().then(setPushState);
  }, []);

  // Keyboard users have no way to dismiss the mobile drawer otherwise -- the
  // overlay only closes on click/tap.
  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mobileOpen]);

  const togglePush = async () => {
    if (pushBusy) return;
    setPushBusy(true);
    try {
      if (pushState === 'subscribed') {
        await disablePush();
        setPushState('unsubscribed');
      } else {
        const ok = await enablePush();
        setPushState(ok ? 'subscribed' : 'unsubscribed');
        if (!ok) alert("Couldn't enable reminders -- notifications may be blocked in your browser settings.");
      }
    } finally {
      setPushBusy(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) return null;

  const items = NAV_ITEMS.filter((i) => !i.adminOnly || user.is_admin);

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <Link to="/dashboard" className="flex items-center gap-2 font-display font-extrabold text-lg text-ink-900 px-5 py-5">
        <span className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white flex items-center justify-center text-sm shadow-sm">
          B
        </span>
        Acelume
      </Link>

      <nav className="flex-1 px-3 space-y-1">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
              }`
            }
          >
            <i className={`${item.icon} w-4 text-center`} />
            {t(item.labelKey)}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 pb-2">
        <LanguageSwitcher />
      </div>

      <div className="p-3 border-t border-ink-100">
        <div className="flex items-center gap-3 px-2 py-2">
          <Avatar name={user.username} size={36} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink-900 truncate">{user.username}</p>
            <p className="text-xs text-ink-400 truncate">{user.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full mt-1 flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-ink-500 hover:bg-ink-100 hover:text-danger-600 transition-colors"
        >
          <i className="fa-solid fa-arrow-right-from-bracket w-4 text-center" />
          Log out
        </button>
      </div>
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

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-ink-900/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-72 bg-white h-full shadow-pop animate-fade-in">{sidebarContent}</aside>
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-ink-100 h-16 flex items-center justify-between px-4 sm:px-6">
          <button className="lg:hidden p-2 -ml-2 text-ink-700" onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <i className="fa-solid fa-bars text-lg" />
          </button>

          <div className="hidden lg:block" />

          <div className="flex items-center gap-3">
            {pushState !== 'unsupported' && (
              <button
                onClick={togglePush}
                disabled={pushBusy}
                title={pushState === 'subscribed' ? 'Daily reminders on -- tap to turn off' : 'Get a reminder if you miss practicing'}
                aria-label={pushState === 'subscribed' ? 'Daily reminders on -- tap to turn off' : 'Get a reminder if you miss practicing'}
                className={`w-9 h-9 rounded-full flex items-center justify-center text-sm transition-colors ${
                  pushState === 'subscribed' ? 'bg-brand-50 text-brand-600' : 'bg-ink-100 text-ink-400 hover:text-ink-600'
                }`}
              >
                <i className={pushState === 'subscribed' ? 'fa-solid fa-bell' : 'fa-regular fa-bell'} />
              </button>
            )}
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

        <main id="main-content" className="flex-1 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
