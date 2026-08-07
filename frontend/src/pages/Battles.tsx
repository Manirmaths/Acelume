import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { Battle as BattleType, BattleQuestion, BattleResult, Subject } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import QuestionText from '../components/ui/QuestionText';
import LiveBattle from '../components/LiveBattle';
import MathText from '../components/ui/MathText';
import { Select } from '../components/ui/Input';
import useDocumentMeta from '../hooks/useDocumentMeta';

const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const;

/** Lobby: start a challenge or join one with a code. */
function Lobby() {
  const navigate = useNavigate();
  const [subject, setSubject] = useState('Mathematics');
  const [count, setCount] = useState(5);
  const [mode, setMode] = useState<'async' | 'live'>('async');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: subjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.get<Subject[]>('/api/subjects'),
  });

  const create = async (vsBot = false) => {
    setBusy(true);
    setError(null);
    try {
      const b = await api.post<BattleType>('/api/battles', {
        subject, questions: count, mode, vs_bot: vsBot,
      });
      navigate(`/battles/${b.code}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start a challenge.');
    } finally {
      setBusy(false);
    }
  };

  const join = async () => {
    if (!code.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.post<BattleType>(`/api/battles/${code.trim().toUpperCase()}/join`);
      navigate(`/battles/${code.trim().toUpperCase()}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not join that challenge.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">
        <i className="fa-solid fa-swords text-brand-500 mr-2" aria-hidden="true" />
        Challenge a friend
      </h1>
      <p className="text-ink-500 mb-6">
        You both get the same questions and answer whenever you like. Getting more right always
        beats being fast.
      </p>

      {error && <p className="text-sm text-danger-600 mb-4" role="alert">{error}</p>}

      <Card padding="lg" className="mb-4">
        <h2 className="font-display font-bold text-sm text-ink-900 mb-3">Start a challenge</h2>
        <div className="grid sm:grid-cols-2 gap-3 mb-4">
          <Select label="Subject" value={subject} onChange={(e) => setSubject(e.target.value)}>
            {subjects?.map((s) => (
              <option key={s.name} value={s.name}>{s.name}</option>
            ))}
          </Select>
          <Select label="Questions" value={count} onChange={(e) => setCount(Number(e.target.value))}>
            <option value={5}>5 questions</option>
            <option value={10}>10 questions</option>
          </Select>
        </div>
        <div className="flex items-center gap-1 p-1 bg-ink-100 rounded-xl w-fit mb-4">
          {([
            { key: 'async' as const, label: 'Any time', hint: 'Answer whenever you like' },
            { key: 'live' as const, label: 'Live', hint: 'Same question, same moment' },
          ]).map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => setMode(m.key)}
              aria-pressed={mode === m.key}
              className={`px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-colors ${
                mode === m.key ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-800'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-400 mb-4">
          {mode === 'live'
            ? 'Both of you answer the same question at the same time, 30 seconds each. Starts as soon as they join.'
            : 'You each answer in your own time. The result settles once you have both finished.'}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => create(false)} disabled={busy}>
            {busy ? 'Creating…' : 'Challenge a friend'}
          </Button>
          {/* Solves the 10pm-with-nobody-online case. A challenge that only
              works when your friends are awake is a feature that mostly does
              not exist. The opponent is always labelled a practice opponent —
              see backend/app/bots.py for why that is non-negotiable. */}
          <Button variant="outline" onClick={() => create(true)} disabled={busy}>
            <i className="fa-solid fa-robot mr-2" aria-hidden="true" />
            Play now
          </Button>
        </div>
        <p className="text-xs text-ink-400 mt-2">
          No one around? "Play now" matches you with a practice opponent at your level.
          Those results do not count towards the league.
        </p>
      </Card>

      <Card padding="lg">
        <h2 className="font-display font-bold text-sm text-ink-900 mb-3">Join with a code</h2>
        <div className="flex gap-2">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="ABC123"
            maxLength={6}
            aria-label="Challenge code"
            className="flex-1 rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm font-mono tracking-widest uppercase focus:border-brand-400 outline-none"
          />
          <Button variant="outline" onClick={join} disabled={busy || !code.trim()}>
            Join
          </Button>
        </div>
      </Card>
    </div>
  );
}

/** Playing: answer the fixed question set. Answers are graded server-side. */
function Play({ code, onDone }: { code: string; onDone: () => void }) {
  const [questions, setQuestions] = useState<BattleQuestion[] | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, { selected: string; seconds: number }>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const startedAt = useRef<number>(Date.now());

  useEffect(() => {
    api
      .get<BattleQuestion[]>(`/api/battles/${code}/questions`)
      .then(setQuestions)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not load the challenge.'));
  }, [code]);

  useEffect(() => {
    startedAt.current = Date.now();
  }, [index]);

  if (error) return <p className="text-sm text-danger-600 p-6" role="alert">{error}</p>;
  if (!questions) return <Spinner className="w-8 h-8 mt-16" />;

  const q = questions[index];
  const isLast = index === questions.length - 1;

  const choose = (key: string) => {
    const seconds = Math.round((Date.now() - startedAt.current) / 1000);
    setAnswers((prev) => ({ ...prev, [q.id]: { selected: key, seconds } }));
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.post(`/api/battles/${code}/submit`, { answers });
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit.');
      setSubmitting(false);
    }
  };

  const picked = answers[q.id]?.selected;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-ink-400">
          Question {index + 1} of {questions.length}
        </span>
        <span className="text-xs font-mono text-ink-400">{code}</span>
      </div>

      <Card padding="lg">
        <div className="font-semibold text-ink-900 mb-4 leading-relaxed">
          <QuestionText text={q.question_text} />
        </div>
        {q.image_url && (
          <img src={q.image_url} alt="" className="w-full max-h-64 object-contain rounded-xl border border-ink-100 mb-4" />
        )}
        <div className="space-y-2">
          {OPTION_KEYS.map((key) => {
            const text = { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d }[key];
            const selected = picked === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => choose(key)}
                aria-pressed={selected}
                className={`w-full text-left text-sm rounded-xl border px-3.5 py-2.5 transition-colors ${
                  selected
                    ? 'border-brand-500 bg-brand-50 text-ink-900'
                    : 'border-ink-200 hover:border-brand-300 hover:bg-brand-50/50'
                }`}
              >
                <span className="font-bold mr-2">{key}.</span>
                <MathText text={text} />
              </button>
            );
          })}
        </div>

        {/* No feedback until submission -- the server withholds correct
            answers until this player has finished, so there is nothing to
            reveal here even if we wanted to. */}
        <div className="flex justify-between items-center mt-6">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
            disabled={index === 0}
          >
            Back
          </Button>
          {isLast ? (
            <Button onClick={submit} disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit answers'}
            </Button>
          ) : (
            <Button onClick={() => setIndex((i) => i + 1)}>Next</Button>
          )}
        </div>
      </Card>

      <p className="text-xs text-ink-400 mt-4 text-center">
        You can change any answer until you submit. Unanswered questions simply score nothing.
      </p>
    </div>
  );
}

/** Result: side-by-side comparison plus the answer review. */
function Result({ code }: { code: string }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['battle', code],
    queryFn: () => api.get<BattleResult>(`/api/battles/${code}`),
    // The opponent may still be playing; poll gently rather than making the
    // student refresh manually.
    refetchInterval: (q) => (q.state.data?.outcome === 'waiting' ? 15000 : false),
  });

  if (isLoading || !data) return <Spinner className="w-8 h-8 mt-16" />;

  const opponentNoun = data.opponent?.is_bot ? data.opponent.username : 'Your opponent';
  const headline =
    data.outcome === 'won' ? 'You won' :
    data.outcome === 'lost' ? `${opponentNoun} won` :
    data.outcome === 'draw' ? 'A draw' : 'Waiting for your opponent';

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1 text-center">{headline}</h1>
      <p className="text-ink-500 mb-6 text-center text-sm">{data.subject} · {data.code}</p>

      <Card padding="lg" className="mb-6">
        <div className="grid grid-cols-2 gap-4 text-center">
          {[data.you, data.opponent].map((side, i) => (
            <div key={i}>
              {/* A bot is always visibly a bot, and is called a practice
                  opponent rather than an opponent. Never inferable-only. */}
              <p className="text-xs font-semibold text-ink-400 mb-1">
                {i === 0
                  ? 'You'
                  : side?.is_bot
                    ? (
                      <>
                        <i className="fa-solid fa-robot mr-1" aria-hidden="true" />
                        {side.username} · practice opponent
                      </>
                    )
                    : 'Opponent'}
              </p>
              <p className="font-display font-extrabold text-2xl text-ink-900">
                {side ? side.score : '—'}
              </p>
              <p className="text-xs text-ink-500 mt-1">
                {side
                  ? side.submitted
                    ? `${side.attempted} attempted${side.avg_correct_seconds !== null ? ` · ${side.avg_correct_seconds}s avg` : ''}`
                    : 'Still playing'
                  : 'Nobody joined yet'}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {data.vs_bot && (
        <p className="text-xs text-ink-400 mb-6 text-center">
          {data.opponent?.bot_blurb} Practice results do not count towards the league.
        </p>
      )}

      {data.outcome === 'waiting' && !data.vs_bot && (
        <Card padding="md" className="mb-6 bg-info-50 border-info-100">
          <p className="text-sm text-info-700">
            <i className="fa-solid fa-share-nodes mr-1.5" aria-hidden="true" />
            Share the code <span className="font-mono font-bold">{data.code}</span> so they can
            play. This updates on its own when they finish.
          </p>
        </Card>
      )}

      {data.review.length > 0 && (
        <>
          <h2 className="font-display font-bold text-sm text-ink-900 mb-3">Answer review</h2>
          <div className="space-y-3 mb-6">
            {data.review.map((r, i) => {
              const right = r.your_answer === r.correct_option;
              return (
                <Card key={r.question_id} padding="md">
                  <div className="font-semibold text-ink-900 mb-2 text-sm leading-relaxed">
                    <span className="text-ink-400 font-normal">{i + 1}.</span>{' '}
                    <QuestionText text={r.question_text} />
                  </div>
                  <p className={`text-xs font-semibold ${right ? 'text-success-600' : 'text-danger-600'}`}>
                    <i className={`fa-solid ${right ? 'fa-circle-check' : 'fa-circle-xmark'} mr-1`} aria-hidden="true" />
                    You answered {r.your_answer || '—'} · correct answer {r.correct_option}
                  </p>
                  {r.explanation && (
                    <p className="text-xs text-ink-500 mt-2 leading-relaxed">
                      <MathText text={r.explanation} />
                    </p>
                  )}
                </Card>
              );
            })}
          </div>
        </>
      )}

      <div className="flex flex-wrap justify-center gap-3">
        <Link to="/battles">
          <Button variant="outline">New challenge</Button>
        </Link>
        <Button onClick={() => refetch()}>Refresh</Button>
      </div>
    </div>
  );
}

export default function Battles() {
  const { code } = useParams();
  useDocumentMeta('Quiz battles', 'Challenge a friend to the same set of questions.');
  const [phase, setPhase] = useState<'loading' | 'play' | 'result'>('loading');

  const { data } = useQuery({
    queryKey: ['battle-state', code],
    queryFn: () => api.get<BattleResult>(`/api/battles/${code}`),
    enabled: !!code,
  });

  // Read the mode from the existing GET. Do NOT call /join here: opening a
  // battle link would then silently enter you into it and consume the second
  // player slot.
  const isLive = data?.mode === 'live';

  useEffect(() => {
    if (!code) return;
    if (data) setPhase(data.you.submitted ? 'result' : 'play');
  }, [code, data]);

  const content = useMemo(() => {
    if (!code) return <Lobby />;
    if (phase === 'loading') return <Spinner className="w-8 h-8 mt-16" />;
    if (phase === 'play') {
      // Live battles are paced by the server clock, so they use their own
      // surface rather than the self-paced async one.
      return isLive
        ? <LiveBattle code={code} onFinished={() => setPhase('result')} />
        : <Play code={code} onDone={() => setPhase('result')} />;
    }
    return <Result code={code} />;
  }, [code, phase, isLive]);

  return content;
}
