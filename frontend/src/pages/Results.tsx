import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { QuizResults, AchievementsResponse } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import MathText from '../components/ui/MathText';
import QuestionText from '../components/ui/QuestionText';
import AskAcelume from '../components/AskAcelume';

export default function Results() {
  const { attemptId = '' } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['results', attemptId],
    queryFn: () => api.get<QuizResults>(`/api/quiz/${attemptId}/results`),
  });

  // Piggyback on the results page load to check for newly-earned badges --
  // this endpoint evaluates + persists unlocks, so it's safe to call here.
  const { data: achievements } = useQuery({
    queryKey: ['achievements-check', attemptId],
    queryFn: () => api.get<AchievementsResponse>('/api/achievements'),
    enabled: !!data,
  });
  const newlyUnlocked = achievements?.items.filter((a) => a.newly_unlocked) ?? [];

  const toggleMark = async (questionId: number, marked: boolean) => {
    await api.post(`/api/review/${questionId}/${marked ? 'unmark' : 'mark'}`);
    queryClient.invalidateQueries({ queryKey: ['results', attemptId] });
  };

  const retakeWrong = async () => {
    try {
      const newAttempt = await api.post<{ attempt_id: number }>(`/api/quiz/${attemptId}/retake-wrong`);
      navigate(`/quiz-attempt/${newAttempt.attempt_id}`);
    } catch {
      alert('Not enough wrong questions to retake (need at least 3).');
    }
  };

  if (isLoading) return <Spinner className="w-8 h-8 mt-16" />;
  if (error || !data) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16">
        <EmptyState icon="fa-solid fa-triangle-exclamation" title="Couldn't load results" />
      </div>
    );
  }

  const pct = data.total > 0 ? Math.round((data.score / data.total) * 100) : 0;
  const tone = pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'danger';

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      {newlyUnlocked.length > 0 && (
        <div className="mb-6 space-y-2">
          {newlyUnlocked.map((a) => (
            <Card key={a.code} padding="md" className="bg-warning-50 border-warning-200 flex items-center gap-3 animate-fade-in">
              <div className="w-10 h-10 rounded-full bg-warning-500 text-white flex items-center justify-center text-base flex-shrink-0">
                <i className={a.icon} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-display font-bold text-sm text-ink-900">Achievement unlocked: {a.title}</p>
                <p className="text-xs text-ink-500">{a.description}</p>
              </div>
              <Link to="/achievements" className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex-shrink-0">
                View all
              </Link>
            </Card>
          ))}
        </div>
      )}

      <div className="text-center mb-8">
        <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-3">Quiz complete</h1>
        <div
          className={`inline-flex flex-col items-center justify-center w-28 h-28 rounded-full font-display font-extrabold text-2xl ${
            tone === 'success' ? 'bg-success-50 text-success-600' : tone === 'warning' ? 'bg-warning-50 text-warning-600' : 'bg-danger-50 text-danger-600'
          }`}
        >
          {data.score}/{data.total}
          <span className="text-xs font-semibold mt-0.5">{pct}%</span>
        </div>
      </div>

      {data.personal_best && (
        <Card
          padding="md"
          className={`mb-6 ${
            data.personal_best.is_best
              ? 'bg-success-50 border-success-200'
              : data.personal_best.is_baseline
                ? 'bg-info-50 border-info-100'
                : 'bg-ink-50 border-ink-100'
          }`}
        >
          <div className="flex items-start gap-3">
            <i
              className={`mt-0.5 ${
                data.personal_best.is_best
                  ? 'fa-solid fa-arrow-trend-up text-success-600'
                  : data.personal_best.is_baseline
                    ? 'fa-solid fa-flag text-info-500'
                    : 'fa-solid fa-bullseye text-ink-400'
              }`}
              aria-hidden="true"
            />
            <div className="min-w-0">
              {/* The message is composed server-side so the wording -- and
                  crucially "percentage points", not "percent" -- cannot drift
                  between the API and the UI. */}
              <p className="text-sm font-medium text-ink-800">{data.personal_best.message}</p>
              {data.personal_best.previous_best_pct !== null && (
                <p className="text-xs text-ink-500 mt-1">
                  This attempt {data.personal_best.current_pct}% · your best{' '}
                  {Math.max(data.personal_best.previous_best_pct, data.personal_best.current_pct)}% ·{' '}
                  {data.personal_best.attempts} comparable attempts
                </p>
              )}
            </div>
          </div>
        </Card>
      )}

      <div className="flex flex-wrap justify-center gap-3 mb-8">
        <Button variant="outline" onClick={retakeWrong} icon={<i className="fa-solid fa-rotate-left" />}>
          Retake wrong only
        </Button>
        <Link to="/subjects">
          <Button icon={<i className="fa-solid fa-arrow-right" />}>Practice more</Button>
        </Link>
      </div>

      <div className="space-y-3">
        {data.items.map((item, i) => (
          <Card key={item.question_id} padding="md">
            <div className="font-semibold text-ink-900 mb-2 leading-relaxed">
              <span className="text-ink-400 font-normal">{i + 1}.</span> <QuestionText text={item.question_text} />
            </div>
            {item.image_url && (
              <img src={item.image_url} alt="Question diagram" className="w-full max-h-56 object-contain rounded-lg border border-ink-100 mb-3 bg-ink-50" />
            )}
            <div className="flex flex-wrap gap-2 mb-2">
              <Badge tone={item.is_correct ? 'success' : 'danger'}>Your answer: {item.selected_option}</Badge>
              {!item.is_correct && <Badge tone="success">Correct: {item.correct_option}</Badge>}
            </div>
            {item.explanation && <p className="text-sm text-ink-500 mb-3 leading-relaxed"><MathText text={item.explanation} /></p>}
            <div className="flex items-center gap-4">
              <button
                onClick={() => toggleMark(item.question_id, item.is_marked)}
                className="text-xs font-semibold text-brand-600 hover:text-brand-700 inline-flex items-center gap-1"
              >
                <i className={item.is_marked ? 'fa-solid fa-bookmark' : 'fa-regular fa-bookmark'} />
                {item.is_marked ? 'Unmark' : 'Mark for review'}
              </button>
            </div>
            {/* Offered on every question, not only the wrong ones. A student
                who guessed correctly has exactly the same gap as one who
                guessed wrong -- hiding the tutor behind a red badge means the
                lucky guess goes unexamined, which is the answer most worth
                examining. The prompts differ by outcome instead. */}
            <AskAcelume questionId={item.question_id} wasCorrect={item.is_correct} />
          </Card>
        ))}
      </div>
    </div>
  );
}
