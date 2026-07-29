import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { ApiError } from '../api/client';
import Button from '../components/ui/Button';
import { Input, PasswordInput } from '../components/ui/Input';
import Card from '../components/ui/Card';
import useDocumentMeta from '../hooks/useDocumentMeta';

export default function Login() {
  useDocumentMeta('Log in', 'Log in to your Acelume account to continue your JAMB, WAEC and NECO practice.');
  const { login } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-16 px-4 sm:px-6">
      <Card padding="lg" className="animate-fade-in">
        <h1 className="font-display font-extrabold text-2xl text-ink-900 text-center mb-1">Welcome back</h1>
        <p className="text-center text-sm text-ink-500 mb-6">Log in to keep your streak going.</p>

        {error && (
          <div className="bg-danger-50 text-danger-600 text-sm rounded-xl px-4 py-3 mb-4 flex items-center gap-2">
            <i className="fa-solid fa-circle-exclamation" /> {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
          <Input type="email" label={t('auth.emailLabel')} required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          <div>
            <PasswordInput label={t('auth.passwordLabel')} required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            <div className="text-right mt-1.5">
              <Link to="/forgot-password" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                {t('auth.forgotPassword')}
              </Link>
            </div>
          </div>
          <Button type="submit" fullWidth size="lg" loading={busy}>
            {busy ? 'Logging in…' : t('auth.loginButton')}
          </Button>
        </form>

        <p className="text-center text-sm text-ink-500 mt-5">
          Don't have an account? <Link to="/register" className="text-brand-600 font-semibold">Register</Link>
        </p>
      </Card>
    </div>
  );
}
