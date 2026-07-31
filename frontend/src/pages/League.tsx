import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { League as LeagueData } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Avatar from '../components/ui/Avatar';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import useDocumentMeta from '../hooks/useDocumentMeta';

/**
 * Zones carry a label and an icon as well as colour, so the ranking is
 * readable without colour vision. Demotion is styled soberly rather than
 * alarmingly -- the spec asks for no humiliating treatment of students near
 * the bottom.
 */
const ZONE: Record<string, { label: string; row: string; badge: string; icon: string }> = {
  promotion: {
    label: 'Promotion',
    row: 'bg-success-50/60',
    badge: 'bg-success-100 text-success-700',
    icon: 'fa-solid fa-arrow-up',
  },
  safe: { label: 'Safe', row: '', badge: 'bg-ink-100 text-ink-500', icon: 'fa-solid fa-minus' },
  demotion: {
    label: 'Relegation',
    row: 'bg-ink-50',
    badge: 'bg-ink-100 text-ink-500',
    icon: 'fa-solid fa-arrow-down',
  },
};

export default function League() {
  const qc = useQueryClient();
  const [confirmOut, setConfirmOut] = useState(false);
  useDocumentMeta('Weekly league', 'See how this week of learning compares with your group.');

  const { data, isLoading } = useQuery({
    queryKey: ['league'],
    queryFn: () => api.get<LeagueData>('/api/leagues'),
  });

  const optOut = useMutation({
    mutationFn: (opted_out: boolean) => api.put<LeagueData>('/api/leagues/opt-out', { opted_out }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['league'] });
      setConfirmOut(false);
    },
  });

  if (isLoading) return <Spinner className="w-8 h-8 mt-16" />;
  if (!data) return null;

  if (data.opted_out) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16">
        <EmptyState
          icon="fa-solid fa-user-shield"
          title="You're not in the weekly league"
          description="Everything else works exactly as before — lessons, practice, mocks, streaks and achievements are all unaffected."
          action={
            <Button onClick={() => optOut.mutate(false)} disabled={optOut.isPending}>
              {optOut.isPending ? 'Joining…' : 'Join the league'}
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-1">
        <h1 className="font-display font-extrabold text-2xl text-ink-900">
          <i className="fa-solid fa-shield-halved text-brand-500 mr-2" aria-hidden="true" />
          {data.tier_label} league
        </h1>
        <span className="text-xs font-semibold text-ink-500 mt-2">
          {data.days_remaining === 0
            ? 'Ends today'
            : `${data.days_remaining} day${data.days_remaining === 1 ? '' : 's'} left`}
        </span>
      </div>
      <p className="text-ink-500 mb-6">
        Ranked on this week's learning — correcting mistakes, passing reviews and mastering
        topics count for far more than answering easy questions.
      </p>

      {data.entries.length === 0 ? (
        <Card padding="lg">
          <EmptyState
            icon="fa-solid fa-shield-halved"
            title="You'll join this week's group on your next answer"
            description="Groups are about 20 students at the same level, so you're never up against people far ahead of you."
          />
        </Card>
      ) : (
        <Card padding="none" className="overflow-hidden mb-4">
          <ul className="divide-y divide-ink-100">
            {data.entries.map((e) => {
              const zone = ZONE[e.zone] ?? ZONE.safe;
              return (
                <li
                  key={e.rank}
                  className={`flex items-center gap-3 px-4 py-3 ${e.is_you ? 'bg-brand-50/70' : zone.row}`}
                >
                  <span className="w-6 text-sm font-bold text-ink-500 tabular-nums text-right">
                    {e.rank}
                  </span>
                  <Avatar name={e.username} size={32} />
                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm truncate ${
                        e.is_you ? 'font-bold text-brand-700' : 'font-semibold text-ink-900'
                      }`}
                    >
                      {e.username}
                      {e.is_you && <span className="ml-2 text-xs font-medium text-brand-500">(you)</span>}
                    </p>
                  </div>
                  <span
                    className={`text-[11px] font-semibold rounded-full px-2 py-0.5 flex-shrink-0 ${zone.badge}`}
                  >
                    <i className={`${zone.icon} mr-1`} aria-hidden="true" />
                    {zone.label}
                  </span>
                  <span className="text-sm font-bold text-ink-900 w-12 text-right tabular-nums">
                    {e.points}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      <p className="text-xs text-ink-400 leading-relaxed mb-6">
        Top {data.promote_top} move up next week. The bottom {data.demote_bottom} who took part move
        down — if you don't play, nothing happens to your place.
      </p>

      {!confirmOut ? (
        <button
          onClick={() => setConfirmOut(true)}
          className="text-xs font-semibold text-ink-400 hover:text-ink-700 underline"
        >
          Leave the weekly league
        </button>
      ) : (
        <Card padding="md" className="bg-ink-50">
          <p className="text-sm text-ink-700 mb-3">
            Leaving hides the leaderboard. Your lessons, practice, streaks, achievements and
            progress are all unaffected, and you can come back any time.
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => optOut.mutate(true)} disabled={optOut.isPending}>
              {optOut.isPending ? 'Leaving…' : 'Leave'}
            </Button>
            <Button size="sm" onClick={() => setConfirmOut(false)}>Stay</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
