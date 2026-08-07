import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { QuizAttempt } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';

const SUBJECTS = [
  'Mathematics', 'English', 'Physics', 'Chemistry', 'Biology',
  'Geography', 'Economics', 'Literature', 'Government', 'Commerce', 'Accounting',
];

/**
 * Rush — three strikes, escalating difficulty.
 *
 * Sits beside Blitz rather than replacing it, the way chess.com runs Puzzle
 * Rush and Puzzle Storm together. The difference is the whole design: a timer
 * makes a student hurry, a strike count makes them careful, then greedy as the
 * run builds, then careful again. It also makes a personal best mean
 * something, because two Rush runs are directly comparable in a way two timed
 * quizzes are not.
 */
export default function Rush() {
  const navigate = useNavigate();
  const [subject, setSubject] = useState('Mathematics');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    if (starting) return;
    setStarting(true);
    setError(null);
    try {
      const attempt = await api.post<QuizAttempt>('/api/rush/start', { subject });
      navigate(`/quiz-attempt/${attempt.attempt_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start a Rush run.');
      setStarting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">
        <i className="fa-solid fa-fire-flame-curved text-danger-500 mr-2" aria-hidden="true" />
        Rush
      </h1>
      <p className="text-ink-500 mb-6">
        Questions get harder as you go. Three wrong and the run is over.
      </p>

      <Card padding="lg">
        <label className="block text-sm font-semibold text-ink-700 mb-2" htmlFor="rush-subject">
          Subject
        </label>
        <select
          id="rush-subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="w-full text-sm rounded-xl border border-ink-200 px-3 py-2.5 mb-4 focus:outline-none focus:ring-2 focus:ring-brand-200"
        >
          {SUBJECTS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <div className="flex items-center gap-2 mb-5 text-sm text-ink-600">
          <span className="text-ink-400">Lives</span>
          {[0, 1, 2].map((i) => (
            <i key={i} className="fa-solid fa-heart text-danger-400" aria-hidden="true" />
          ))}
          <span className="text-xs text-ink-400 ml-1">no timer — take your time</span>
        </div>

        <Button fullWidth size="lg" onClick={start} disabled={starting}>
          {starting ? 'Starting…' : 'Start Rush'}
        </Button>

        {error && <p className="text-sm text-danger-500 mt-3" role="alert">{error}</p>}
      </Card>

      <p className="text-xs text-ink-400 mt-4 text-center leading-relaxed">
        Everyone fails out eventually — that is the point. Your run ends a few questions
        past where you are comfortable, which is where practice actually works.
      </p>
    </div>
  );
}
