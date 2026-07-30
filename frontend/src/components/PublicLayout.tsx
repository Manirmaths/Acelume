import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import Button from './ui/Button';
import LanguageSwitcher from './ui/LanguageSwitcher';
import Logo from './ui/Logo';

export default function PublicLayout() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const location = useLocation();
  const isAuthPage = location.pathname === '/login' || location.pathname === '/register';
  const isHome = location.pathname === '/';

  return (
    <div className="min-h-screen flex flex-col bg-ink-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-white focus:text-ink-900 focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-pop focus:font-semibold"
      >
        Skip to main content
      </a>
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-ink-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="flex items-center gap-2 font-display font-extrabold text-lg text-ink-900 flex-shrink-0">
              <Logo className="w-8 h-8 rounded-xl shadow-sm" />
              Acelume
            </Link>

            {isHome && (
              <nav className="hidden sm:flex items-center gap-6">
                <a href="#features" className="text-sm font-semibold text-ink-500 hover:text-ink-900 transition-colors">Features</a>
                <a href="#how-it-works" className="text-sm font-semibold text-ink-500 hover:text-ink-900 transition-colors">How it works</a>
              </nav>
            )}

            {!isAuthPage && (
              <div className="flex items-center gap-3 flex-shrink-0">
                <LanguageSwitcher />
                {user ? (
                  <Link to="/dashboard">
                    <Button size="sm">{t('nav.goToDashboard')}</Button>
                  </Link>
                ) : (
                  <>
                    <Link to="/login">
                      <Button variant="ghost" size="sm">{t('nav.login')}</Button>
                    </Link>
                    <Link to="/register">
                      <Button size="sm">{t('nav.getStarted')}</Button>
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      <main id="main-content" className="flex-1">
        <Outlet />
      </main>

      <footer className="bg-ink-900 text-ink-400 py-10 mt-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm">
          <p>&copy; {new Date().getFullYear()} Acelume by Arewa Tutorials. Your ambition. Within reach.</p>
          <div className="flex items-center gap-4">
            <Link to="/privacy" className="hover:text-ink-200 transition-colors">Privacy Policy</Link>
            <p className="flex items-center gap-1 text-ink-500">
              Made with <i className="fa-solid fa-heart text-flame-500" /> for Nigerian students
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
