import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { ApiError } from '../api/client';
import Button from '../components/ui/Button';
import { Input, PasswordInput } from '../components/ui/Input';
import Card from '../components/ui/Card';
import useDocumentMeta from '../hooks/useDocumentMeta';

export default function Register() {
  useDocumentMeta(
    'Sign up free',
    'Create a free Acelume account for JAMB, WAEC and NECO practice questions, an AI tutor, and a full CBT mock exam.'
  );
  const { register } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      await register(username, email, password);
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
        <h1 className="font-display font-extrabold text-2xl text-ink-900 text-center mb-1">Create your account</h1>
        <p className="text-center text-sm text-ink-500 mb-6">Free forever. Every subject included.</p>

        {error && (
          <div className="bg-danger-50 text-danger-600 text-sm rounded-xl px-4 py-3 mb-4 flex items-center gap-2">
            <i className="fa-solid fa-circle-exclamation" /> {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
          <Input label={t('auth.usernameLabel')} required minLength={2} maxLength={20} value={username} onChange={(e) => setUsername(e.target.value)} placeholder="chidera_reads" />
          <Input type="email" label={t('auth.emailLabel')} required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          <PasswordInput label={t('auth.passwordLabel')} required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
          <PasswordInput label="Confirm password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="••••••••" />
          <Button type="submit" fullWidth size="lg" loading={busy}>
            {busy ? 'Creating account…' : t('auth.registerButton')}
          </Button>
        </form>

        <p className="text-center text-sm text-ink-500 mt-5">
          Already have an account? <Link to="/login" className="text-brand-600 font-semibold">Log in</Link>
        </p>
      </Card>
    </div>
  );
}
