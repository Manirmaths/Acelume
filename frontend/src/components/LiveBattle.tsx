import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { BattleLive, BattleQuestion } from '../api/types';
import Card from './ui/Card';
import Spinner from './ui/Spinner';
import QuestionText from './ui/QuestionText';
import MathText from './ui/MathText';

const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const;
const POLL_MS = 3000;

/**
 * Live battle play surface.
 *
 * Polls a stateless endpoint rather than holding a websocket. On the mobile
 * networks this app actually runs on, a socket turns every stall or IP change
 * into a broken session needing reconciliation; a poll just asks again and is
 * told where the battle is. See the note in backend/app/routers/battles.py.
 *
 * The local countdown is cosmetic. `seconds_remaining` from the server is
 * authoritative and overwrites it on every poll, so a phone with a wrong or
 * throttled clock cannot drift out of sync with the opponent.
 */
export default function LiveBattle({ code, onFinished }: { code: string; onFinished: () => void }) {
  const [state, setState] = useState<BattleLive | null>(null);
  const [questions, setQuestions] = useState<BattleQuestion[] | null>(null);
  const [answered, setAnswered] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const finishing = useRef(false);

  // Held in a ref so the poll effect does not depend on the callback's
  // identity. If it did, an inline arrow from the parent would tear down and
  // rebuild the interval on every render -- and since each rebuild polls
  // immediately and every poll sets state, that is an unbounded request loop
  // pointed at the API. The parent currently memoises it; this makes that a
  // convenience rather than a load-bearing detail.
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  // Question set is fixed at creation, so it only needs fetching once.
  useEffect(() => {
    api
      .get<BattleQuestion[]>(`/api/battles/${code}/questions`)
      .then(setQuestions)
      .catch(() => setQuestions([]));
  }, [code]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const s = await api.get<BattleLive>(`/api/battles/${code}/live`);
        if (cancelled) return;
        setState(s);
        setCountdown(s.seconds_remaining);

        if (s.finished && !finishing.current) {
          finishing.current = true;
          // Either player may finish the battle; grading is idempotent.
          await api.post(`/api/battles/${code}/live/finish`).catch(() => {});
          onFinishedRef.current();
        }
      } catch (e) {
        // A failed poll is not an error state -- it is a bad moment on a
        // mobile network. Keep the last known state and try again.
        if (!cancelled && e instanceof ApiError && e.status === 400) {
          setError(e.message);
        }
      }
    };

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [code]);

  // Cosmetic tick between polls so the timer doesn't visibly jump in 3s steps.
  useEffect(() => {
    if (countdown === null) return;
    const t = setTimeout(() => setCountdown((c) => (c === null ? null : Math.max(0, c - 1))), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  const choose = async (index: number, key: string) => {
    setAnswered((prev) => ({ ...prev, [index]: key }));
    try {
      const s = await api.post<BattleLive>(`/api/battles/${code}/live/answer`, {
        index,
        selected: key,
      });
      setState(s);
    } catch (e) {
      // 409 means the window closed as they tapped. Roll the local choice
      // back rather than showing a selection the server did not accept.
      setAnswered((prev) => {
        const next = { ...prev };
        delete next[index];
        return next;
      });
      if (e instanceof ApiError && e.status !== 409) setError(e.message);
    }
  };

  if (error) return <p className="text-sm text-danger-600 p-6" role="alert">{error}</p>;
  if (!state || !questions) return <Spinner className="w-8 h-8 mt-16" />;

  if (!state.started) {
    return (
      <div className="max-w-xl mx-auto px-4 sm:px-6 py-16 text-center">
        <Spinner className="w-8 h-8 mx-auto mb-4" />
        <p className="font-display font-bold text-ink-900 mb-1">Waiting for your opponent</p>
        <p className="text-sm text-ink-500">
          Share the code <span className="font-mono font-bold">{state.code}</span>. The battle
          starts the moment they join.
        </p>
      </div>
    );
  }

  const index = state.current_index;
  if (index === null) return <Spinner className="w-8 h-8 mt-16" />;

  // By id, never questions[index]: /questions omits any question that has been
  // deleted since the battle was created, which shifts every later position
  // and would show one question while the server grades another.
  const q = questions.find((x) => x.id === state.current_question_id);
  const picked = answered[index];
  const urgent = (countdown ?? 30) <= 5;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-ink-400">
          Question {index + 1} of {state.total}
        </span>
        <span
          className={`text-sm font-mono font-bold tabular-nums ${urgent ? 'text-danger-600' : 'text-ink-700'}`}
          role="timer"
          aria-live="off"
        >
          {countdown ?? '--'}s
        </span>
      </div>

      <div className="flex items-center gap-2 mb-4 text-xs text-ink-500">
        <span
          className={`w-2 h-2 rounded-full ${state.opponent_present ? 'bg-success-500' : 'bg-ink-300'}`}
          aria-hidden="true"
        />
        {/* Never phrased as "disconnected" -- losing signal does not forfeit,
            and telling a student their opponent dropped invites the wrong
            conclusion about what happens next. */}
        {state.opponent_present ? 'Opponent is here' : 'Opponent is quiet'}
        <span className="text-ink-300">·</span>
        answered {state.opponent_answered}/{state.total}
      </div>

      <Card padding="lg">
        {q ? (
          <div className="font-semibold text-ink-900 mb-4 leading-relaxed">
            <QuestionText text={q.question_text} />
          </div>
        ) : (
          <p className="text-sm text-ink-500 mb-4">
            This question is unavailable. It will pass in a moment and the battle continues —
            neither of you is scored on it.
          </p>
        )}
        {q?.image_url && (
          <img src={q.image_url} alt="" className="w-full max-h-56 object-contain rounded-xl border border-ink-100 mb-4" />
        )}
        <div className="space-y-2">
          {OPTION_KEYS.map((key) => {
            const text = q ? { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d }[key] : '';
            const selected = picked === key;
            return (
              <button
                key={key}
                type="button"
                disabled={!!picked || !q}
                onClick={() => choose(index, key)}
                aria-pressed={selected}
                className={`w-full text-left text-sm rounded-xl border px-3.5 py-2.5 transition-colors ${
                  selected
                    ? 'border-brand-500 bg-brand-50 text-ink-900'
                    : 'border-ink-200 hover:border-brand-300 hover:bg-brand-50/50 disabled:opacity-60'
                }`}
              >
                <span className="font-bold mr-2">{key}.</span>
                <MathText text={text} />
              </button>
            );
          })}
        </div>

        {picked && (
          <p className="text-xs text-ink-400 mt-4">
            Answer locked in. The next question opens automatically.
          </p>
        )}
      </Card>

      <p className="text-xs text-ink-400 mt-4 text-center leading-relaxed">
        Everyone gets the same time on each question. If your connection drops, whatever you have
        already answered still counts.
      </p>
    </div>
  );
}
