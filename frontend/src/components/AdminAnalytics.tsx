import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { Analytics } from '../api/types';
import Card from './ui/Card';
import Spinner from './ui/Spinner';

/**
 * Retention and funnel, for deciding whether a trial worked.
 *
 * Built around one question: after a teacher introduces the app and then stops
 * mentioning it, do those students come back on their own? Totals cannot
 * answer that — they only ever go up, which is why they always feel like
 * progress and never settle an argument.
 *
 * Two display rules follow from that, and both matter:
 *
 *   1. A cohort too young for a checkpoint shows "—", never 0%. Zero would
 *      make every recent week look like a disaster and bury the real signal.
 *   2. Week two is given its own headline. It is the number the trial exists
 *      to produce, and it should not be something you have to hunt for in a
 *      table.
 */

function pct(value: number | null | undefined) {
  return value == null ? <span className="text-ink-300">—</span> : `${value}%`;
}

/** Green above 20%, amber 10–20%, grey below. Deliberately unambitious
 *  thresholds: for a study app used by teenagers outside school hours,
 *  20% still practising unprompted after two weeks is a real result. */
function tone(value: number | null | undefined) {
  if (value == null) return 'text-ink-300';
  if (value >= 20) return 'text-success-600 font-semibold';
  if (value >= 10) return 'text-warning-600 font-semibold';
  return 'text-ink-500';
}

/**
 * Turn a failure into something the reader can act on.
 *
 * The first version of this screen said "Couldn't load analytics." and nothing
 * else, which is the exact failure shape that made the dashboard bug so hard
 * to pin down: it tells you something is wrong and gives you no way to find
 * out what. A 404 and a 403 need completely different responses, and only the
 * status code distinguishes them.
 */
function explain(error: unknown): { title: string; detail: string } {
  const status = error instanceof ApiError ? error.status : null;

  if (status === 404) {
    return {
      title: 'The API does not have this endpoint yet',
      detail:
        'The web app has deployed but the backend has not. Render builds them separately and ' +
        'the Python service is slower. Check the acelume-api service in Render — once it finishes ' +
        'deploying, reload this page.',
    };
  }
  if (status === 401) {
    return {
      title: 'Your session has ended',
      detail: 'Sign in again and come back to this tab.',
    };
  }
  if (status === 403) {
    return {
      title: 'This account is not an admin',
      detail: 'Retention data is admin-only. Promote the account from the Users tab.',
    };
  }
  if (status && status >= 500) {
    return {
      title: `The server errored (${status})`,
      detail:
        'Check the acelume-api logs in Render for the traceback. This is a bug, not a ' +
        'configuration problem.',
    };
  }
  return {
    title: "Couldn't reach the API",
    detail:
      'Usually a connection problem, or the backend is still cold-starting on the free plan ' +
      '(that can take up to a minute). Try again in a moment.',
  };
}

export default function AdminAnalytics() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['admin-analytics'],
    queryFn: () => api.get<Analytics>('/api/admin/analytics'),
    retry: false,
  });

  if (isLoading) return <Spinner className="w-8 h-8 mt-12" />;

  if (error || !data) {
    const { title, detail } = explain(error);
    const status = error instanceof ApiError ? error.status : null;
    return (
      <Card padding="lg">
        <div className="flex items-start gap-3">
          <i className="fa-solid fa-triangle-exclamation text-warning-500 mt-0.5" aria-hidden="true" />
          <div className="min-w-0">
            <p className="font-display font-bold text-ink-900">
              {title}
              {status && <span className="font-normal text-ink-400 text-sm ml-2">HTTP {status}</span>}
            </p>
            <p className="text-sm text-ink-600 mt-1 leading-relaxed">{detail}</p>
            {error instanceof ApiError && error.message && (
              <p className="text-xs text-ink-400 mt-2 font-mono">{error.message}</p>
            )}
            <button
              onClick={() => refetch()}
              className="mt-3 text-xs font-semibold text-brand-600 hover:text-brand-700"
            >
              Try again
            </button>
          </div>
        </div>
      </Card>
    );
  }

  const f = data.funnel;
  const peak = Math.max(1, ...data.daily.map((d) => d.signups));

  return (
    <div className="space-y-6">
      {/* The headline. Everything else on this page is context for it. */}
      <Card padding="lg">
        <p className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-1">
          Still practising after two weeks
        </p>
        <div className="flex items-baseline gap-3">
          <span className={`font-display font-extrabold text-4xl ${tone(data.week_two_return_pct)}`}>
            {data.week_two_return_pct == null ? '—' : `${data.week_two_return_pct}%`}
          </span>
          <span className="text-sm text-ink-500">
            {data.students_measured > 0
              ? `${data.students_measured} students across ${data.cohorts_measured} cohort${data.cohorts_measured === 1 ? '' : 's'}`
              : 'no cohort is old enough yet'}
          </span>
        </div>
        <p className="text-xs text-ink-400 mt-2 leading-relaxed">
          The only number that survives a teacher trial. Week-one activity measures
          compliance with a teacher; this measures whether students came back once
          nobody was asking them to.
        </p>
      </Card>

      {/* Funnel */}
      <Card padding="lg">
        <h3 className="font-display font-bold text-ink-900 mb-4">
          Where new students stop
          <span className="font-normal text-xs text-ink-400 ml-2">last 30 days</span>
        </h3>

        <div className="space-y-2">
          {[
            { label: 'Signed up', value: f.signups },
            { label: 'Answered one question', value: f.answered_one },
            { label: 'Answered ten', value: f.answered_ten },
            { label: 'Finished a quiz', value: f.completed_attempt },
          ].map((step) => {
            const share = f.signups > 0 ? Math.round((100 * step.value) / f.signups) : 0;
            return (
              <div key={step.label} className="flex items-center gap-3">
                <span className="text-sm text-ink-600 w-48 flex-shrink-0">{step.label}</span>
                <div className="flex-1 h-5 rounded-lg bg-ink-100 overflow-hidden" aria-hidden="true">
                  <div className="h-full bg-brand-500/80" style={{ width: `${share}%` }} />
                </div>
                <span className="text-sm tabular-nums w-20 text-right text-ink-700">
                  {step.value} <span className="text-ink-400 text-xs">{share}%</span>
                </span>
              </div>
            );
          })}
        </div>

        <div className="mt-4 pt-4 border-t border-ink-100 flex flex-wrap gap-6">
          <div>
            <p className="text-xs text-ink-400">Median signup → first question</p>
            <p className="font-display font-bold text-ink-900">
              {f.median_seconds_to_first_question == null
                ? '—'
                : `${f.median_seconds_to_first_question}s`}
            </p>
          </div>
          <div>
            <p className="text-xs text-ink-400">
              Within {data.time_to_value_target_seconds}s target
            </p>
            <p className={`font-display font-bold ${tone(f.within_target_pct)}`}>
              {pct(f.within_target_pct)}
            </p>
          </div>
        </div>
      </Card>

      {/* Cohorts */}
      <Card padding="lg">
        <h3 className="font-display font-bold text-ink-900 mb-1">Weekly cohorts</h3>
        <p className="text-xs text-ink-400 mb-4">
          "Returned" means answered a question, not opened the app. "—" means the cohort
          is too young for that checkpoint yet.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-ink-400 text-left border-b border-ink-100">
                <th className="pb-2 font-semibold">Week of</th>
                <th className="pb-2 font-semibold text-right">Signups</th>
                <th className="pb-2 font-semibold text-right">Started</th>
                <th className="pb-2 font-semibold text-right">Day 1</th>
                <th className="pb-2 font-semibold text-right">Day 7</th>
                <th className="pb-2 font-semibold text-right">Day 14</th>
              </tr>
            </thead>
            <tbody>
              {data.cohorts.map((c) => (
                <tr key={c.week_start} className="border-b border-ink-50 last:border-0">
                  <td className="py-2 text-ink-700">{c.week_start}</td>
                  <td className="py-2 text-right tabular-nums text-ink-900 font-semibold">{c.signups}</td>
                  <td className="py-2 text-right tabular-nums text-ink-500">
                    {c.activated}
                    <span className="text-ink-300 text-xs ml-1">
                      {c.signups > 0 ? `${Math.round((100 * c.activated) / c.signups)}%` : ''}
                    </span>
                  </td>
                  <td className={`py-2 text-right tabular-nums ${tone(c.d1)}`}>{pct(c.d1)}</td>
                  <td className={`py-2 text-right tabular-nums ${tone(c.d7)}`}>{pct(c.d7)}</td>
                  <td className={`py-2 text-right tabular-nums ${tone(c.d14)}`}>{pct(c.d14)}</td>
                </tr>
              ))}
              {data.cohorts.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-ink-400">
                    No signups yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Daily signups — the shape that shows when a trial actually started. */}
      <Card padding="lg">
        <h3 className="font-display font-bold text-ink-900 mb-4">
          Signups per day
          <span className="font-normal text-xs text-ink-400 ml-2">
            solid = started practising
          </span>
        </h3>
        <div className="flex items-end gap-0.5 h-24">
          {data.daily.map((d) => (
            <div
              key={d.date}
              className="flex-1 flex flex-col justify-end min-w-0"
              title={`${d.date}: ${d.signups} signups, ${d.activated} started`}
            >
              <div
                className="bg-ink-200 rounded-t-sm"
                style={{ height: `${(100 * (d.signups - d.activated)) / peak}%` }}
              />
              <div
                className="bg-brand-500 rounded-b-sm"
                style={{ height: `${(100 * d.activated) / peak}%` }}
              />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
