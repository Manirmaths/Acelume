import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Dashboard as DashboardData } from '../api/types';
import Card from '../components/ui/Card';
import HubGrid, { type HubLink } from '../components/ui/HubGrid';
import Insights from '../components/Insights';

function Stat({ icon, label, value, tone }: { icon: string; label: string; value: string | number; tone: string }) {
  return (
    <Card padding="md" className="flex items-center gap-3">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${tone}`} aria-hidden="true">
        <i className={icon} />
      </div>
      <div className="min-w-0">
        <p className="font-display font-extrabold text-xl text-ink-900 leading-none">{value}</p>
        <p className="text-xs text-ink-500 mt-1 font-medium truncate">{label}</p>
      </div>
    </Card>
  );
}

export default function ProgressHub() {
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardData>('/api/dashboard'),
  });

  const links: HubLink[] = [
    {
      to: '/achievements',
      icon: 'fa-solid fa-medal',
      title: 'Achievements',
      description: 'What you have unlocked, and what is close.',
    },
    {
      to: '/school',
      icon: 'fa-solid fa-school',
      title: 'Your school',
      description: 'Represent your school and see how it ranks in your state and nationally.',
    },
    {
      to: '/league',
      icon: 'fa-solid fa-shield-halved',
      title: 'Weekly league',
      description: 'This week against nineteen students at your tier. Resets every Monday.',
    },
    {
      to: '/leaderboard',
      icon: 'fa-solid fa-ranking-star',
      title: 'Leaderboard',
      description: 'How you compare across the whole of Acelume.',
    },
    {
      to: '/study-planner',
      icon: 'fa-solid fa-calendar-days',
      title: 'Study planner',
      description: 'Your schedule between now and exam day.',
    },
  ];

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900">Progress</h1>
      <p className="text-ink-500 mt-1 mb-6">How much you have learned, and how it is holding up.</p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat
          icon="fa-solid fa-star"
          label="Total XP"
          value={data?.points ?? '—'}
          tone="bg-brand-50 text-brand-600"
        />
        <Stat
          icon="fa-solid fa-fire"
          label="Day streak"
          value={data?.current_streak ?? '—'}
          tone="bg-flame-500/10 text-flame-500"
        />
        <Stat
          icon="fa-solid fa-chart-line"
          label="Level"
          value={data?.level?.level ?? '—'}
          tone="bg-info-50 text-info-500"
        />
        <Stat
          icon="fa-solid fa-bolt"
          label="Best Blitz"
          value={data?.blitz_best ?? '—'}
          tone="bg-ink-100 text-ink-500"
        />
      </div>

      <Insights />

      <HubGrid links={links} />
    </div>
  );
}
