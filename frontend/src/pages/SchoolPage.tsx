import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { MySchool, SchoolLeaderboardEntry, School } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';

/**
 * School clubs.
 *
 * Two things govern this screen and neither is negotiable:
 *
 * 1. **No other student is ever named.** A student sees their own
 *    contribution and their school's aggregate; every other child is a number
 *    inside a total. A public per-pupil ranking attached to a named school is
 *    a safeguarding problem, not a leaderboard. The API enforces this too.
 *
 * 2. **The ranked figure is per member, not the total.** Ranking on totals
 *    sorts the table by enrolment and tells a student at a small school they
 *    cannot win however hard they work.
 */
export default function SchoolPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [newName, setNewName] = useState('');
  const [state, setState] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState<'national' | 'state'>('national');

  const { data: mine, isLoading } = useQuery({
    queryKey: ['my-school'],
    queryFn: () => api.get<MySchool | null>('/api/schools/me'),
    retry: false,
  });

  const { data: results } = useQuery({
    queryKey: ['school-search', query],
    queryFn: () => api.get<School[]>(`/api/schools/search?q=${encodeURIComponent(query)}`),
    enabled: !mine && query.length >= 2,
  });

  const { data: board } = useQuery({
    queryKey: ['school-leaderboard', scope, mine?.school.state],
    queryFn: () =>
      api.get<SchoolLeaderboardEntry[]>(
        scope === 'state' && mine?.school.state
          ? `/api/schools/leaderboard?state=${encodeURIComponent(mine.school.state)}`
          : '/api/schools/leaderboard',
      ),
    enabled: !!mine,
  });

  const join = async (body: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await api.post('/api/schools/join', body);
      queryClient.invalidateQueries({ queryKey: ['my-school'] });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not join that school.');
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) return <Spinner className="w-8 h-8 mt-16" />;

  if (!mine) {
    return (
      <div className="max-w-xl mx-auto px-4 sm:px-6 py-8">
        <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">Your school</h1>
        <p className="text-ink-500 mb-6">
          Represent your school. Every question you get right adds to their week.
        </p>

        <Card padding="lg" className="mb-4">
          <label className="block text-sm font-semibold text-ink-700 mb-2" htmlFor="school-search">
            Find your school
          </label>
          <input
            id="school-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Start typing the name…"
            className="w-full text-sm rounded-xl border border-ink-200 px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-200"
          />

          {results && results.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {results.map((s) => (
                <button
                  key={s.id}
                  onClick={() => join({ school_id: s.id })}
                  disabled={busy}
                  className="w-full text-left rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm hover:border-brand-300 hover:bg-brand-50/50 disabled:opacity-50"
                >
                  <span className="font-semibold text-ink-900">{s.name}</span>
                  {s.state && <span className="text-ink-400 text-xs ml-2">{s.state}</span>}
                </button>
              ))}
            </div>
          )}

          {query.length >= 2 && results && results.length === 0 && (
            <p className="text-xs text-ink-400 mt-3">
              Not listed? Add it below — you'd be the first from your school.
            </p>
          )}
        </Card>

        <Card padding="lg">
          <h2 className="font-display font-bold text-sm text-ink-900 mb-3">Add your school</h2>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="School name"
            className="w-full text-sm rounded-xl border border-ink-200 px-3.5 py-2.5 mb-2 focus:outline-none focus:ring-2 focus:ring-brand-200"
          />
          <input
            value={state}
            onChange={(e) => setState(e.target.value)}
            placeholder="State (e.g. Sokoto)"
            className="w-full text-sm rounded-xl border border-ink-200 px-3.5 py-2.5 mb-3 focus:outline-none focus:ring-2 focus:ring-brand-200"
          />
          <Button
            fullWidth
            onClick={() => join({ name: newName, state })}
            disabled={busy || newName.trim().length < 3}
          >
            Add and join
          </Button>
        </Card>

        {error && <p className="text-sm text-danger-500 mt-3" role="alert">{error}</p>}
      </div>
    );
  }

  const movement =
    mine.last_week_national_rank != null && mine.national_rank != null
      ? mine.last_week_national_rank - mine.national_rank
      : null;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">
        {mine.school.name}
      </h1>
      <p className="text-ink-500 mb-6 text-sm">
        {mine.school.state && <>{mine.school.state} · </>}
        {mine.active_members} active this week
        {mine.school.status === 'community' && (
          <span className="text-ink-400"> · added by a student</span>
        )}
      </p>

      <Card padding="lg" className="mb-6">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="font-display font-extrabold text-2xl text-ink-900 leading-none">
              {mine.points_per_member}
            </p>
            <p className="text-xs text-ink-500 mt-1.5">points per member</p>
          </div>
          <div>
            <p className="font-display font-extrabold text-2xl text-ink-900 leading-none">
              {mine.national_rank ? `#${mine.national_rank}` : '—'}
            </p>
            <p className="text-xs text-ink-500 mt-1.5">
              national
              {movement != null && movement !== 0 && (
                <span className={movement > 0 ? 'text-success-600' : 'text-ink-400'}>
                  {' '}
                  {movement > 0 ? `▲${movement}` : `▼${Math.abs(movement)}`}
                </span>
              )}
            </p>
          </div>
          <div>
            {/* The only individual number anywhere on this page, and it is
                the student's own. */}
            <p className="font-display font-extrabold text-2xl text-brand-600 leading-none">
              {mine.your_contribution}
            </p>
            <p className="text-xs text-ink-500 mt-1.5">your points</p>
          </div>
        </div>
      </Card>

      <div className="flex gap-2 mb-3">
        {(['national', 'state'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            disabled={s === 'state' && !mine.school.state}
            className={`text-sm font-semibold px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40 ${
              scope === s ? 'bg-brand-50 text-brand-700' : 'text-ink-500 hover:bg-ink-100'
            }`}
          >
            {s === 'national' ? 'National' : mine.school.state || 'State'}
          </button>
        ))}
      </div>

      <Card padding="md">
        {board && board.length > 0 ? (
          <div className="divide-y divide-ink-100">
            {board.map((row) => (
              <div
                key={row.school_id}
                className={`flex items-center gap-3 py-2.5 ${
                  row.school_id === mine.school.id ? 'font-semibold text-brand-700' : 'text-ink-700'
                }`}
              >
                <span className="w-8 text-sm tabular-nums text-ink-400">#{row.rank}</span>
                <span className="flex-1 min-w-0 truncate text-sm">{row.name}</span>
                <span className="text-xs text-ink-400 tabular-nums">{row.active_members} active</span>
                <span className="text-sm font-bold tabular-nums w-14 text-right">
                  {row.points_per_member}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-500 py-4 text-center">
            No schools ranked yet this week. Get your school on the board.
          </p>
        )}
      </Card>

      <p className="text-xs text-ink-400 mt-4 leading-relaxed">
        Schools are ranked by points per active member, so a small school can beat a large
        one. Individual students are never shown publicly — only your school's totals.
        {mine.can_change_after && <> You can change school from {mine.can_change_after}.</>}
      </p>
    </div>
  );
}
