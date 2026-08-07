import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { DailyQuestion, DailyQuestionResult } from '../api/types';
import Card from './ui/Card';
import Button from './ui/Button';
import MathText from './ui/MathText';
import QuestionText from './ui/QuestionText';
import AskAcelume from './AskAcelume';

const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const;

/**
 * Today's question -- one question, the same one for every student.
 *
 * The comparison line ("68% got this right", "faster than 74% today") is the
 * feature, not decoration. A personalised daily mission is a chore; a shared
 * question is something two students can argue about on WhatsApp, which is
 * how anything spreads in this market. Everything here is built to be worth
 * screenshotting.
 *
 * Renders nothing at all if there is no question for today. A broken or empty
 * card at the top of the dashboard is worse than no card.
 */
export default function DailyQuestionCard() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<DailyQuestionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openedAt] = useState(() => Date.now());

  const { data, isLoading } = useQuery({
    queryKey: ['daily-question'],
    queryFn: () => api.get<DailyQuestion>('/api/daily-question'),
    retry: false,
  });

  if (isLoading || !data) return null;

  const answered = data.answered || result !== null;
  const correctOption = result?.correct_option ?? data.correct_option;
  const explanation = result?.explanation ?? data.explanation;
  const isCorrect = result?.is_correct ?? data.is_correct;
  const yourAnswer = result ? selected : data.your_answer;
  const streak = result?.streak ?? data.streak;

  const submit = async () => {
    if (!selected || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<DailyQuestionResult>('/api/daily-question/answer', {
        selected_option: selected,
        answer_seconds: Math.max(0, Math.round((Date.now() - openedAt) / 1000)),
      });
      setResult(res);
      // XP, streaks and the daily ring all move on a correct answer.
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit your answer.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card padding="lg" className="mb-6 border-brand-200 bg-gradient-to-br from-brand-50/70 to-white">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <i className="fa-solid fa-calendar-day text-brand-500" aria-hidden="true" />
          <h2 className="font-display font-bold text-ink-900 truncate">Today's Question</h2>
          {data.subject && (
            <span className="hidden sm:inline text-xs text-ink-400 flex-shrink-0">· {data.subject}</span>
          )}
        </div>
        {streak > 0 && (
          <span
            className="flex items-center gap-1.5 rounded-full bg-flame-500/10 text-flame-500 px-2.5 py-1 text-xs font-bold flex-shrink-0"
            title={`${streak}-day Daily Question streak`}
          >
            <i className="fa-solid fa-fire" aria-hidden="true" />
            {streak}
          </span>
        )}
      </div>

      <div className="font-semibold text-ink-900 mb-3 leading-relaxed">
        <QuestionText text={data.question_text} />
      </div>

      {data.image_url && (
        <img
          src={data.image_url}
          alt="Question diagram"
          className="w-full max-h-56 object-contain rounded-xl border border-ink-100 mb-3 bg-white"
        />
      )}

      <div className="space-y-2">
        {OPTION_KEYS.map((key) => {
          const text = { A: data.option_a, B: data.option_b, C: data.option_c, D: data.option_d }[key];
          const isPicked = (answered ? yourAnswer : selected) === key;
          const isRight = answered && correctOption === key;

          let tone = 'border-ink-200 bg-white hover:border-brand-300 hover:bg-brand-50/50';
          if (answered && isRight) tone = 'border-success-500 bg-success-50 text-success-700';
          else if (answered && isPicked) tone = 'border-danger-400 bg-danger-50 text-danger-600';
          else if (isPicked) tone = 'border-brand-500 bg-brand-50 text-ink-900';

          return (
            <button
              key={key}
              type="button"
              disabled={answered || submitting}
              onClick={() => setSelected(key)}
              aria-pressed={isPicked}
              className={`w-full text-left text-sm rounded-xl border px-3.5 py-2.5 transition-colors disabled:cursor-default ${tone}`}
            >
              <span className="font-bold mr-2">{key}.</span>
              <MathText text={text} />
              {answered && isRight && <i className="fa-solid fa-check float-right mt-0.5" aria-hidden="true" />}
            </button>
          );
        })}
      </div>

      {!answered ? (
        <Button fullWidth className="mt-3" onClick={submit} disabled={!selected || submitting}>
          {submitting ? 'Checking…' : 'Submit'}
        </Button>
      ) : (
        <div className="mt-3">
          <p className={`text-sm font-semibold ${isCorrect ? 'text-success-600' : 'text-warning-600'}`}>
            {isCorrect ? 'Correct.' : `Not quite — the answer is ${correctOption}.`}
          </p>

          {explanation && (
            <p className="text-sm text-ink-600 mt-1.5 leading-relaxed">
              <MathText text={explanation} />
            </p>
          )}

          {/* The social payload. Deliberately phrased as facts about the day
              rather than a score, so it reads the same to a student who got
              it wrong. */}
          <p className="text-xs text-ink-500 mt-3">
            {(result?.percent_correct ?? data.percent_correct) !== null && (
              <>
                {result?.percent_correct ?? data.percent_correct}% of students got this right today
              </>
            )}
            {result?.faster_than_percent != null && (
              <> · you were faster than {result.faster_than_percent}% of them</>
            )}
          </p>

          <AskAcelume questionId={data.question_id} wasCorrect={!!isCorrect} />
        </div>
      )}

      {error && <p className="text-xs text-danger-500 mt-2" role="alert">{error}</p>}
    </Card>
  );
}
