import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { SubjectRating } from '../api/types';
import Card from './ui/Card';

/**
 * Predicted exam score per subject.
 *
 * This is the visible surface of an internal Glicko-2 rating, and the framing
 * is the whole design. A raw rating labelled "1180" means nothing to a JAMB
 * candidate and quietly demoralises a weak one; "62/100" is the number they
 * already think in. Same mathematics underneath — the rating never leaves the
 * server.
 *
 * Two rules the UI must not break:
 *
 *   1. Only a RISE is announced. A fall shows the new number without a red
 *      arrow, because a drop displayed on its own teaches a struggling student
 *      to avoid hard questions — precisely backwards. When it falls, what they
 *      need is the topic to fix, not the bad news.
 *   2. While provisional, say so in words instead of showing a confident
 *      number the model has no right to be confident about.
 */
export default function PredictedScores() {
  const { data } = useQuery({
    queryKey: ['subject-ratings'],
    queryFn: () => api.get<SubjectRating[]>('/api/dashboard/ratings'),
    retry: false,
  });

  if (!data || data.length === 0) return null;

  return (
    <Card padding="lg" className="mb-6">
      <div className="flex items-baseline justify-between gap-3 mb-1">
        <h2 className="font-display font-bold text-ink-900">If the exam were tomorrow</h2>
        <span className="text-xs text-ink-400">updates as you practise</span>
      </div>
      <p className="text-xs text-ink-500 mb-4">
        Estimated from the difficulty of the questions you actually get right.
      </p>

      <div className="space-y-2.5">
        {data.map((r) => (
          <div key={r.subject} className="flex items-center gap-3">
            <span className="text-sm text-ink-700 w-28 flex-shrink-0 truncate">{r.subject}</span>

            <div className="flex-1 h-2 rounded-full bg-ink-100 overflow-hidden" aria-hidden="true">
              <div
                className={`h-full rounded-full ${r.provisional ? 'bg-ink-300' : 'bg-brand-500'}`}
                style={{ width: `${r.predicted_score}%` }}
              />
            </div>

            {r.provisional ? (
              <span className="text-xs text-ink-400 w-32 text-right flex-shrink-0">
                still getting a read
              </span>
            ) : (
              <span className="w-32 text-right flex-shrink-0 tabular-nums">
                <span className="font-display font-bold text-ink-900">{r.predicted_score}</span>
                <span className="text-ink-400 text-xs">/100</span>
                <span className="text-ink-300 text-xs ml-1">
                  ±{Math.max(1, Math.round((r.range_high - r.range_low) / 2))}
                </span>
                {/* Rises only. See the note above. */}
                {r.week_delta != null && r.week_delta > 0 && (
                  <span className="text-success-600 text-xs font-semibold ml-1.5">
                    ▲{r.week_delta}
                  </span>
                )}
              </span>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
