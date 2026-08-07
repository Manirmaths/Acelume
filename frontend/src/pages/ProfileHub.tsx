import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Avatar from '../components/ui/Avatar';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import LanguageSwitcher from '../components/ui/LanguageSwitcher';
import HubGrid, { type HubLink } from '../components/ui/HubGrid';
import { disablePush, enablePush, getPushState, type PushSupport } from '../lib/push';

export default function ProfileHub() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [pushState, setPushState] = useState<PushSupport>('unsupported');
  const [pushBusy, setPushBusy] = useState(false);

  useEffect(() => {
    getPushState().then(setPushState);
  }, []);

  if (!user) return null;

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
        if (!ok) {
          alert("Couldn't enable reminders -- notifications may be blocked in your browser settings.");
        }
      }
    } finally {
      setPushBusy(false);
    }
  };

  const links: HubLink[] = [
    {
      to: '/family',
      icon: 'fa-solid fa-people-roof',
      title: 'Family & tutors',
      description: 'Let a parent, guardian or tutor follow your progress, without sharing your password.',
    },
    ...(user.is_admin
      ? [{
          to: '/admin',
          icon: 'fa-solid fa-user-shield',
          title: 'Admin',
          description: 'Questions, content review and platform settings.',
        }]
      : []),
  ];

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-6">Profile</h1>

      <Card padding="lg" className="flex items-center gap-4 mb-4">
        <Avatar name={user.username} size={56} />
        <div className="min-w-0">
          <p className="font-display font-bold text-lg text-ink-900 truncate">{user.username}</p>
          <p className="text-sm text-ink-500 truncate">{user.email}</p>
        </div>
      </Card>

      <Card padding="lg" className="mb-4">
        <h2 className="font-display font-bold text-ink-900 mb-3">Settings</h2>

        <div className="flex items-center justify-between gap-4 py-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink-900">Daily reminders</p>
            <p className="text-xs text-ink-500 mt-0.5">
              A nudge if you have not practised by the evening.
            </p>
          </div>
          {pushState === 'unsupported' ? (
            <span className="text-xs text-ink-400 flex-shrink-0">Not available on this device</span>
          ) : (
            <Button
              variant={pushState === 'subscribed' ? 'outline' : 'primary'}
              size="sm"
              onClick={togglePush}
              disabled={pushBusy}
            >
              {pushState === 'subscribed' ? 'On' : 'Turn on'}
            </Button>
          )}
        </div>

        <div className="flex items-center justify-between gap-4 py-2 border-t border-ink-100 mt-2 pt-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink-900">Language</p>
            <p className="text-xs text-ink-500 mt-0.5">English or Hausa.</p>
          </div>
          <LanguageSwitcher />
        </div>
      </Card>

      <div className="mb-4">
        <HubGrid links={links} />
      </div>

      <Button
        variant="ghost"
        fullWidth
        onClick={async () => {
          await logout();
          navigate('/login');
        }}
      >
        <i className="fa-solid fa-arrow-right-from-bracket mr-2" />
        Log out
      </Button>
    </div>
  );
}
