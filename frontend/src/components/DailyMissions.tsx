import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { DailyMissions as DailyMissionsData, DailyMission } from '../api/types';
import Card from './ui/Card';

const KIND_ICON: Record<string, string> = {
  progress: 'fa-solid fa-book-open',
  practice: 'fa-solid fa-pen-to-square',
  improvement: 'fa-solid fa-arrow-trend-up',
};

function MissionRow({ mission }: { mission: DailyMission }) {
  const pct = mission.target > 0 ? Math.round((100 * mission.progress) / mission.target) : 0;
  const icon = KIND_ICON[mission.kind] ?? 'fa-solid fa-circle';

  const body = (
    <div className="flex items-start gap-3 py-2.5">
      <div
        className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs ${
          mission.completed ? 'bg-success-500 text-white' : 'bg-ink-100 text-ink-500'
        }`}
        aria-hidden="true"
      >
        <i className={mission.completed ? 'fa-solid fa-check' : icon} />
      </div>
      <div className="flex-1 min-w-0">
        <p
          className={`text-sm font-medium ${
            mission.completed ? 'text-ink-400 line-through' : 'text-ink-800'
          }`}
        >
          {mission.title}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <div className="h-1.5 flex-1 rounded-full bg-ink-100 overflow-hidden">
            <div
              className={`h-full transition-all ${mission.completed ? 'bg-success-500' : 'bg-brand-500'}`}
              style={{ width: `${pct}%` }}
              role="progressbar"
              aria-valuenow={mission.progress}
              aria-valuemin={0}
              aria-valuemax={mission.target}
              aria-label={`${mission.title}: ${mission.progress} of ${mission.target}`}
            />
          </div>
          <span className="text-[11px] text-ink-400 font-semibold flex-shrink-0 tabular-nums">
            {mission.progress}/{mission.target}
          </span>
        </div>
      </div>
    </div>
  );

  if (mission.completed || !mission.action_path) return body;
  return (
    <Link to={mission.action_path} className="block hover:bg-ink-50/60 -mx-2 px-2 rounded-lg transition-colors">
      {body}
    </Link>
  );
}

export default function DailyMissions() {
  const { data, isLoading } = useQuery({
    queryKey: ['missions'],
    queryFn: () => api.get<DailyMissionsData>('/api/missions'),
    retry: false,
  });

  // Missions need a seeded syllabus. Rather than showing a broken card on an
  // instance that has not been set up, render nothing at all.
  if (isLoading || !data || data.items.length === 0) return null;

  const done = data.items.filter((m) => m.completed).length;

  return (
    <Card padding="lg" className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <h2 className="font-display font-bold text-sm text-ink-900">
          <i className="fa-solid fa-list-check text-brand-500 mr-1.5" aria-hidden="true" />
          Today's missions
        </h2>
        <span className="text-xs text-ink-400 font-medium">
          {done}/{data.items.length} done · about {data.total_minutes} min
        </span>
      </div>

      <p className="text-xs text-ink-400 mb-1">
        {data.all_complete ? (
          <>
            <i className="fa-solid fa-gift text-warning-500 mr-1" aria-hidden="true" />
            All done — {data.reward_xp} XP earned. New missions at midnight.
          </>
        ) : (
          /* Reward stated up front rather than revealed on opening: no
             mystery boxes, per the spec's ban on gambling-style mechanics. */
          <>Finish all three to earn {data.reward_xp} XP. Resets at midnight.</>
        )}
      </p>

      <div className="divide-y divide-ink-100">
        {data.items.map((m) => (
          <MissionRow key={m.kind} mission={m} />
        ))}
      </div>
    </Card>
  );
}
