import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../api/client';
import type { Leaderboard as LeaderboardData, Subject } from '../api/types';
import Card from '../components/ui/Card';
import Avatar from '../components/ui/Avatar';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import { Select } from '../components/ui/Input';

const MEDAL_TONE: Record<number, string> = {
  1: 'bg-gradient-to-br from-yellow-300 to-yellow-500 text-white',
  2: 'bg-gradient-to-br from-gray-300 to-gray-400 text-white',
  3: 'bg-gradient-to-br from-amber-500 to-amber-700 text-white',
};

function RankBadge({ rank }: { rank: number }) {
  const medal = MEDAL_TONE[rank];
  if (medal) {
    return (
      <div className={`w-9 h-9 rounded-full flex items-center justify-center font-display font-extrabold text-sm shadow-sm ${medal}`}>
        {rank}
      </div>
    );
  }
  return (
    <div className="w-9 h-9 rounded-full flex items-center justify-center font-display font-bold text-sm text-ink-500 bg-ink-100">
      {rank}
    </div>
  );
}

export default function Leaderboard() {
  const [subject, setSubject] = useState('overall');

  const { data: subjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.get<Subject[]>('/api/subjects'),
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['leaderboard', subject],
    queryFn: () =>
      api.get<LeaderboardData>(
        subject === 'overall' ? '/api/leaderboard' : `/api/leaderboard?subject=${encodeURIComponent(subject)}`
      ),
  });

  const youInTop = data?.entries.some((e) => e.is_you) ?? false;

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
        <h1 className="font-display font-extrabold text-2xl text-ink-900">
          <i className="fa-solid fa-ranking-star text-brand-500 mr-2" />
          Leaderboard
        </h1>
        <Select value={subject} onChange={(e) => setSubject(e.target.value)} className="!w-auto !py-1.5 !px-2 !text-sm">
          <option value="overall">Overall</option>
          {subjects?.map((s) => (
            <option key={s.name} value={s.name}>{s.name}</option>
          ))}
        </Select>
      </div>
      <p className="text-ink-500 mb-6">
        {subject === 'overall'
          ? 'See how you stack up against everyone practicing on Acelume.'
          : `Top scorers in ${subject}, based on correct answers.`}
      </p>

      {isLoading && <Spinner className="w-8 h-8 mt-16" />}

      {!isLoading && (error || !data) && (
        <EmptyState icon="fa-solid fa-triangle-exclamation" title="Couldn't load the leaderboard" />
      )}

      {!isLoading && data && (
        <>
          <Card padding="none" className="overflow-hidden">
            {data.entries.length === 0 ? (
              <div className="p-8">
                <EmptyState
                  icon="fa-solid fa-ranking-star"
                  title="No rankings yet"
                  description={
                    subject === 'overall'
                      ? 'Start practicing to earn points and appear on the leaderboard.'
                      : `No one has answered ${subject} questions yet -- be the first!`
                  }
                />
              </div>
            ) : (
              <ul className="divide-y divide-ink-100">
                {data.entries.map((entry) => (
                  <li
                    key={entry.rank}
                    className={`flex items-center gap-4 px-5 py-3.5 transition-colors ${
                      entry.is_you ? 'bg-brand-50/70' : ''
                    }`}
                  >
                    <RankBadge rank={entry.rank} />
                    <Avatar name={entry.username} size={36} />
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm truncate ${entry.is_you ? 'font-bold text-brand-700' : 'font-semibold text-ink-900'}`}>
                        {entry.username}
                        {entry.is_you && <span className="ml-2 text-xs font-medium text-brand-500">(you)</span>}
                      </p>
                    </div>
                    {entry.current_streak > 0 && (
                      <div className="flex items-center gap-1 text-xs font-bold text-flame-500 flex-shrink-0">
                        <i className="fa-solid fa-fire" />
                        {entry.current_streak}
                      </div>
                    )}
                    <div className="flex items-center gap-1.5 text-sm font-bold text-ink-900 flex-shrink-0 w-16 justify-end">
                      <i className="fa-solid fa-star text-brand-500 text-xs" />
                      {entry.points}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {!youInTop && (
            <Card padding="md" className="mt-4 bg-brand-50 border-brand-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full flex items-center justify-center font-display font-bold text-sm text-brand-700 bg-brand-100">
                  {data.your_rank}
                </div>
                <p className="text-sm font-semibold text-brand-800">Your current rank</p>
              </div>
              <div className="flex items-center gap-1.5 text-sm font-bold text-brand-800">
                <i className="fa-solid fa-star text-xs" />
                {data.your_points}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
