import { Link } from 'react-router-dom';
import type { AnswerQuality, AnswerLabel } from '../api/types';
import Card from './ui/Card';

const LABEL_ORDER: AnswerLabel[] = ['sharp', 'solid', 'lucky', 'slip', 'gap', 'blunder'];

const LABEL_STYLE: Record<AnswerLabel, { title: string; dot: string; text: string }> = {
  sharp: { title: 'Sharp', dot: 'bg-success-500', text: 'text-success-700' },
  solid: { title: 'Solid', dot: 'bg-success-400', text: 'text-success-600' },
  lucky: { title: 'Lucky', dot: 'bg-warning-400', text: 'text-warning-600' },
  slip: { title: 'Slip', dot: 'bg-warning-500', text: 'text-warning-700' },
  gap: { title: 'Gap', dot: 'bg-ink-300', text: 'text-ink-500' },
  blunder: { title: 'Blunder', dot: 'bg-danger-500', text: 'text-danger-600' },
};

/**
 * Post-attempt review, in the spirit of chess.com's Game Review.
 *
 * The thing being borrowed is the VOCABULARY, not the analysis. "You got
 * 9/12" is a grade and stops being informative after the first week. "You
 * slipped on a topic you'd already mastered, here are five questions on it"
 * is a next action.
 *
 * Accuracy is deliberately NOT percent correct — it is weighted, so scraping
 * nine right with three lucky guesses does not read the same as nine clean
 * ones. If it did, it would carry no more information than the fraction it
 * sits next to.
 */
export default function AnswerReview({ quality, subject }: { quality: AnswerQuality; subject?: string | null }) {
  const present = LABEL_ORDER.filter((k) => (quality.counts[k] ?? 0) > 0);
  if (quality.accuracy === null && present.length === 0) return null;

  const focus = quality.focus_topics[0];

  return (
    <Card padding="lg" className="mb-6">
      <div className="flex items-baseline justify-between gap-4 mb-4">
        <div>
          <p className="text-xs font-semibold text-ink-400 uppercase tracking-wide">Accuracy</p>
          <p className="font-display font-extrabold text-3xl text-ink-900 leading-none mt-1">
            {quality.accuracy ?? '—'}
            {quality.accuracy !== null && <span className="text-lg">%</span>}
          </p>
        </div>
        <p className="text-xs text-ink-400 text-right max-w-[45%] leading-snug">
          Weighted by how each answer was earned — not the same as your score.
        </p>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-2 mb-4">
        {present.map((key) => {
          const style = LABEL_STYLE[key];
          return (
            <span key={key} className="inline-flex items-center gap-1.5 text-sm">
              <span className={`w-2 h-2 rounded-full ${style.dot}`} aria-hidden="true" />
              <span className={`font-semibold ${style.text}`}>{style.title}</span>
              <span className="text-ink-500 tabular-nums">{quality.counts[key]}</span>
            </span>
          );
        })}
      </div>

      {quality.headline && (
        <div className="flex items-start gap-3 rounded-xl bg-ink-50 border border-ink-100 p-3">
          <i className="fa-solid fa-circle-exclamation text-warning-500 mt-0.5" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-sm text-ink-800 leading-snug">{quality.headline}</p>
            {focus && subject && (
              <Link
                to={`/quiz?subject=${encodeURIComponent(subject)}&topic=${encodeURIComponent(focus)}&n=5`}
                className="inline-block mt-2 text-xs font-semibold text-brand-600 hover:text-brand-700"
              >
                5 questions on {focus} →
              </Link>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

/** Small inline badge shown against an individual answer. */
export function AnswerLabelBadge({
  label,
  title,
  message,
}: {
  label: AnswerLabel;
  title: string | null;
  message: string | null;
}) {
  const style = LABEL_STYLE[label];
  if (!style) return null;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-semibold ${style.text}`}
      title={message ?? undefined}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} aria-hidden="true" />
      {title ?? style.title}
    </span>
  );
}
