import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { api, ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { Dashboard as DashboardData, QuizAttempt } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import ProgressBar from '../components/ui/ProgressBar';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';

const GOAL_PRESETS = [
  { value: 20, label: 'Casual' },
  { value: 50, label: 'Regular' },
  { value: 100, label: 'Serious' },
  { value: 150, label: 'Intense' },
];

function StatCard({ icon, label, value, tone }: { icon: string; label: string; value: string | number; tone: string }) {
  return (
    <Card padding="md" className="flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-lg flex-shrink-0 ${tone}`}>
        <i className={icon} />
      </div>
      <div>
        <p className="font-display font-extrabold text-2xl text-ink-900 leading-none">{value}</p>
        <p className="text-xs text-ink-500 mt-1 font-medium">{label}</p>
      </div>
    </Card>
  );
}

function DailyGoalRing({ pointsToday, dailyGoal, goalMet }: { pointsToday: number; dailyGoal: number; goalMet: boolean }) {
  const size = 88;
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(1, dailyGoal > 0 ? pointsToday / dailyGoal : 0));
  const offset = circumference * (1 - pct);

  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={stroke} className="text-ink-100" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={goalMet ? 'text-success-500 transition-all duration-500' : 'text-brand-500 transition-all duration-500'}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        {goalMet ? (
          <i className="fa-solid fa-check text-success-500 text-xl" />
        ) : (
          <span className="font-display font-extrabold text-sm text-ink-900">{Math.round(pct * 100)}%</span>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [savingGoal, setSavingGoal] = useState(false);
  const [startingReview, setStartingReview] = useState(false);
  const [startingDiagnostic, setStartingDiagnostic] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardData>('/api/dashboard'),
  });

  const setGoal = async (value: number) => {
    if (savingGoal || value === data?.daily_goal) return;
    setSavingGoal(true);
    try {
      await api.put('/api/dashboard/daily-goal', { daily_goal: value });
      await Promise.all([queryClient.invalidateQueries({ queryKey: ['dashboard'] }), refresh()]);
    } finally {
      setSavingGoal(false);
    }
  };

  const startSmartReview = async () => {
    if (startingReview) return;
    setStartingReview(true);
    try {
      const attempt = await api.post<QuizAttempt>('/api/smart-review/start');
      navigate(`/quiz-attempt/${attempt.attempt_id}`);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : 'Could not start Smart Review.');
      setStartingReview(false);
    }
  };

  const startDiagnostic = async () => {
    if (startingDiagnostic) return;
    setStartingDiagnostic(true);
    try {
      const attempt = await api.post<QuizAttempt>('/api/quiz/start-diagnostic');
      navigate(`/quiz-attempt/${attempt.attempt_id}`);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : 'Could not start the diagnostic.');
      setStartingDiagnostic(false);
    }
  };

  if (isLoading) return <Spinner className="w-8 h-8 mt-16" />;
  if (error || !data) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16">
        <EmptyState icon="fa-solid fa-triangle-exclamation" title="Couldn't load your dashboard" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">Welcome back, {user?.username}</h1>
      <p className="text-ink-500 mb-6">Here's how your practice is going.</p>

      {data.level && (
        <Card padding="md" className="mb-6">
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="w-9 h-9 rounded-xl bg-brand-100 text-brand-700 font-display font-extrabold text-sm flex items-center justify-center flex-shrink-0">
                {data.level.level}
              </span>
              <div className="min-w-0">
                <p className="font-display font-bold text-sm text-ink-900 truncate">
                  Level {data.level.level} · {data.level.title}
                </p>
                {/* Named explicitly so XP never reads as proof of understanding
                    -- mastery lives on the Quest Map, not here. */}
                <p className="text-xs text-ink-400">Based on total practice, not mastery</p>
              </div>
            </div>
            <span className="text-xs font-semibold text-ink-500 flex-shrink-0">
              {data.level.xp_into_level} / {data.level.xp_for_next} XP
            </span>
          </div>
          <div className="h-2 rounded-full bg-ink-100 overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all"
              style={{ width: `${data.level.percent}%` }}
              role="progressbar"
              aria-valuenow={data.level.percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${data.level.percent}% towards level ${data.level.level + 1}`}
            />
          </div>
        </Card>
      )}

      <Card padding="lg" className="mb-6 flex flex-wrap items-center gap-5">
        <DailyGoalRing pointsToday={data.points_today} dailyGoal={data.daily_goal} goalMet={data.goal_met} />
        <div className="flex-1 min-w-[180px]">
          <p className="font-display font-bold text-ink-900">
            {data.goal_met ? (
              <>Daily goal reached! <i className="fa-solid fa-champagne-glasses text-warning-500" /></>
            ) : (
              'Daily goal'
            )}
          </p>
          <p className="text-sm text-ink-500 mb-3">
            {data.points_today} / {data.daily_goal} XP today
          </p>
          <div className="flex flex-wrap gap-1.5">
            {GOAL_PRESETS.map((p) => (
              <button
                key={p.value}
                onClick={() => setGoal(p.value)}
                disabled={savingGoal}
                className={`text-xs font-semibold rounded-full px-3 py-1.5 transition-colors ${
                  data.daily_goal === p.value
                    ? 'bg-brand-500 text-white'
                    : 'bg-ink-100 text-ink-600 hover:bg-ink-200'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <Card padding="lg" className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display font-bold text-sm text-ink-900">
            <i className="fa-solid fa-calendar-week text-brand-500 mr-1.5" />
            This week
          </h2>
          <span className="text-xs text-ink-400 font-medium">{data.current_streak}-day streak</span>
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {data.practice_days.map((d) => (
            <div key={d.date} className="flex flex-col items-center gap-1">
              <span className={`text-[11px] font-semibold ${d.is_today ? 'text-brand-600' : 'text-ink-400'}`}>{d.label}</span>
              <div
                className={`w-full aspect-square rounded-lg flex items-center justify-center text-xs ${
                  d.practiced
                    ? 'bg-success-500 text-white'
                    : d.is_future
                    ? 'bg-ink-50 text-ink-300'
                    : d.is_today
                    ? 'bg-brand-50 text-brand-600 ring-2 ring-brand-300'
                    : 'bg-ink-100 text-ink-400'
                }`}
              >
                {d.practiced ? <i className="fa-solid fa-check" /> : d.is_today ? <i className="fa-regular fa-circle" /> : ''}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Resuming matters more than any stat below it, so it sits first.
          Before this existed, closing the tab mid-quiz silently discarded the
          attempt -- the QuizAttempt row survived but nothing linked to it. */}
      {data.unfinished_attempt && (
        <Card padding="md" className="bg-warning-50 border-warning-100 mb-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-warning-700 font-medium">
            <i className="fa-solid fa-hourglass-half mr-1.5" />
            You have an unfinished {data.unfinished_attempt.subject ?? 'practice'} session —{' '}
            {data.unfinished_attempt.answered} of {data.unfinished_attempt.total} answered.
          </p>
          <Link
            to={
              data.unfinished_attempt.mode === 'mock'
                ? `/mock-attempt/${data.unfinished_attempt.id}`
                : `/quiz-attempt/${data.unfinished_attempt.id}`
            }
          >
            <Button size="sm" icon={<i className="fa-solid fa-play" />}>Resume</Button>
          </Link>
        </Card>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard icon="fa-solid fa-star" label="Total points" value={data.points} tone="bg-brand-50 text-brand-600" />
        <StatCard icon="fa-solid fa-fire" label="Current streak" value={`${data.current_streak}d`} tone="bg-flame-500/10 text-flame-500" />
        {/* Mastery streak sits beside the learning streak on purpose: showing
            up daily and performing well daily are different achievements, and
            collapsing them would let attendance read as competence. */}
        <StatCard
          icon="fa-solid fa-brain"
          label="Mastery streak"
          value={`${data.mastery_streak}d`}
          tone="bg-success-50 text-success-600"
        />
        <StatCard icon="fa-solid fa-bolt" label="Best Blitz" value={data.blitz_best} tone="bg-flame-500/10 text-flame-500" />
      </div>

      {/* Marked questions moved out of the stat grid to make room for Blitz:
          it's an action, not a score, so it reads better as a link. */}
      <div className="grid sm:grid-cols-2 gap-4 mb-6">
        <Link to="/review" className="block">
          <Card padding="md" className="h-full flex items-center justify-between gap-3 hover:border-brand-300 transition-colors">
            <span className="text-sm font-semibold text-ink-700">
              <i className="fa-solid fa-bookmark text-info-500 mr-1.5" />
              {data.review_count} marked question{data.review_count === 1 ? '' : 's'}
            </span>
            <i className="fa-solid fa-chevron-right text-ink-300 text-xs" />
          </Card>
        </Link>
        <Link to="/blitz" className="block">
          <Card padding="md" className="h-full flex items-center justify-between gap-3 hover:border-brand-300 transition-colors">
            <span className="text-sm font-semibold text-ink-700">
              <i className="fa-solid fa-bolt text-flame-500 mr-1.5" />
              {data.blitz_best > 0 ? `Beat your best of ${data.blitz_best}` : 'Try a 3-minute Blitz'}
            </span>
            <i className="fa-solid fa-chevron-right text-ink-300 text-xs" />
          </Card>
        </Link>
      </div>

      {data.due_for_review_count > 0 && (
        <Card padding="md" className="bg-info-50 border-info-100 mb-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-info-700 font-medium">
            <i className="fa-solid fa-clock-rotate-left mr-1.5" />
            {data.due_for_review_count} question{data.due_for_review_count === 1 ? '' : 's'} due for review — Smart Review focuses on what you're about to forget.
          </p>
          <Button size="sm" onClick={startSmartReview} disabled={startingReview}>
            {startingReview ? 'Starting…' : 'Start Smart Review'}
          </Button>
        </Card>
      )}

      <div className="grid sm:grid-cols-2 gap-4 mb-6">
        <Card padding="lg">
          <h2 className="font-display font-bold text-sm text-ink-900 mb-2">
            <i className="fa-solid fa-gauge-high text-brand-500 mr-1.5" />
            Projected JAMB score
          </h2>
          {data.score_estimate.available ? (
            <>
              <p className="font-display font-extrabold text-2xl text-ink-900">
                {data.score_estimate.projected_low}–{data.score_estimate.projected_high}
                <span className="text-sm font-semibold text-ink-400"> / 400</span>
              </p>
              <p className="text-xs text-ink-500 mt-1.5">
                Estimated from your practice accuracy across {data.score_estimate.based_on_answers} answered questions — not an official JAMB score.
              </p>
            </>
          ) : (
            <p className="text-sm text-ink-500">{data.score_estimate.message}</p>
          )}
        </Card>

        <Card padding="lg">
          <h2 className="font-display font-bold text-sm text-ink-900 mb-2">
            <i className="fa-solid fa-crosshairs text-flame-500 mr-1.5" />
            Focus on this
          </h2>
          {data.recommended_topics.length > 0 ? (
            <div className="space-y-1">
              {data.recommended_topics.map((t) => (
                <div key={t.topic} className="flex items-center justify-between text-sm rounded-lg px-2.5 py-2 -mx-2.5 hover:bg-ink-50 transition-colors">
                  <Link
                    to={t.subject ? `/subjects/${encodeURIComponent(t.subject)}/topics/${encodeURIComponent(t.topic)}` : `/quiz?topic=${encodeURIComponent(t.topic)}`}
                    className="font-semibold text-ink-700 hover:text-brand-600 flex-1 min-w-0 truncate"
                  >
                    {t.topic}
                  </Link>
                  <span className="text-xs text-danger-500 font-semibold ml-2 flex-shrink-0">{t.percentage}%</span>
                  <Link
                    to={`/quiz?topic=${encodeURIComponent(t.topic)}`}
                    title="Practice now"
                    className="ml-3 w-6 h-6 rounded-full bg-ink-100 text-ink-400 hover:bg-brand-100 hover:text-brand-600 flex items-center justify-center flex-shrink-0 transition-colors"
                  >
                    <i className="fa-solid fa-play text-[10px]" />
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-500">Practice a few topics and we'll flag the weakest ones here.</p>
          )}
        </Card>
      </div>

      {!data.has_taken_diagnostic && (
        <Card padding="md" className="bg-brand-50 border-brand-100 mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-brand-800 font-semibold">
              <i className="fa-solid fa-circle-info mr-1.5" />
              New here? Take the 33-question diagnostic
            </p>
            <p className="text-xs text-brand-700 mt-1">
              Three questions from every subject — get your topic breakdown and a projected score in one go.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button size="sm" onClick={startDiagnostic} loading={startingDiagnostic}>
              Start diagnostic
            </Button>
            <Link to="/subjects">
              <Button size="sm" variant="ghost">Or pick a subject</Button>
            </Link>
          </div>
        </Card>
      )}

      <Card padding="lg">
        <h2 className="font-display font-bold text-lg text-ink-900 mb-4">Topic performance</h2>
        {data.topic_stats.length > 0 ? (
          <div className="space-y-4">
            {data.topic_stats.map((t) => (
              <div key={t.topic}>
                <div className="flex justify-between text-sm mb-1.5">
                  <span className="font-semibold text-ink-700">{t.topic}</span>
                  <span className="text-ink-400 text-xs font-medium">
                    {t.correct}/{t.total} ({t.percentage}%)
                  </span>
                </div>
                <ProgressBar value={t.percentage} tone={t.percentage >= 70 ? 'success' : t.percentage >= 40 ? 'warning' : 'danger'} />
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="fa-solid fa-chart-line"
            title="No practice data yet"
            description="Take a quiz to start tracking your accuracy by topic."
            action={
              <Link to="/subjects">
                <Button size="sm">Practice now</Button>
              </Link>
            }
          />
        )}
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3 mt-6">
        <Link to="/subjects">
          <Button icon={<i className="fa-solid fa-play" />}>Practice more</Button>
        </Link>
        <div className="flex items-center gap-4">
          <Link to="/achievements" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
            <i className="fa-solid fa-medal mr-1" /> Achievements
          </Link>
          <Link to="/review" className="text-sm font-semibold text-brand-600 hover:text-brand-700">
            View marked questions <i className="fa-solid fa-arrow-right ml-1" />
          </Link>
        </div>
      </div>
    </div>
  );
}
