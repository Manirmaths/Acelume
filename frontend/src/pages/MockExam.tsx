import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { MockNav, MockQuestion } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import MathText from '../components/ui/MathText';
import QuestionText from '../components/ui/QuestionText';

function fmtTime(s: number): string {
  const clamped = Math.max(0, Math.round(s));
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const sec = clamped % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

function Calculator({ onClose }: { onClose: () => void }) {
  const [display, setDisplay] = useState('0');
  const [pending, setPending] = useState<{ value: number; op: string } | null>(null);
  const [justEvaluated, setJustEvaluated] = useState(false);

  const inputDigit = (d: string) => {
    if (justEvaluated) {
      setDisplay(d === '.' ? '0.' : d);
      setJustEvaluated(false);
      return;
    }
    if (d === '.' && display.includes('.')) return;
    setDisplay((prev) => (prev === '0' && d !== '.' ? d : prev + d));
  };

  const applyOp = (op: string) => {
    const current = parseFloat(display);
    if (pending) {
      const result = calc(pending.value, current, pending.op);
      setDisplay(String(result));
      setPending({ value: result, op });
    } else {
      setPending({ value: current, op });
    }
    setJustEvaluated(false);
    setDisplay('0');
  };

  const calc = (a: number, b: number, op: string): number => {
    switch (op) {
      case '+': return a + b;
      case '-': return a - b;
      case '×': return a * b;
      case '÷': return b === 0 ? NaN : a / b;
      default: return b;
    }
  };

  const equals = () => {
    if (!pending) return;
    const result = calc(pending.value, parseFloat(display), pending.op);
    setDisplay(String(result));
    setPending(null);
    setJustEvaluated(true);
  };

  const clear = () => {
    setDisplay('0');
    setPending(null);
    setJustEvaluated(false);
  };

  const buttons = ['7', '8', '9', '÷', '4', '5', '6', '×', '1', '2', '3', '-', '0', '.', '=', '+'];

  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-ink-900/40" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-t-2xl sm:rounded-2xl shadow-pop w-full sm:w-72 p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="font-display font-bold text-sm text-ink-900">Calculator</p>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-700">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>
        <div className="bg-ink-900 text-white text-right text-2xl font-mono rounded-xl px-4 py-3 mb-3 overflow-x-auto">
          {display}
        </div>
        <div className="grid grid-cols-4 gap-2">
          <button onClick={clear} className="col-span-4 py-2.5 rounded-xl bg-danger-50 text-danger-600 font-bold text-sm">C</button>
          {buttons.map((b) => (
            <button
              key={b}
              onClick={() => {
                if (b === '=') equals();
                else if (['+', '-', '×', '÷'].includes(b)) applyOp(b);
                else inputDigit(b);
              }}
              className={`py-2.5 rounded-xl font-semibold text-sm ${
                ['+', '-', '×', '÷', '='].includes(b) ? 'bg-brand-500 text-white' : 'bg-ink-100 text-ink-800'
              }`}
            >
              {b}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function MockExam() {
  const { attemptId = '' } = useParams();
  const navigate = useNavigate();

  const [nav, setNav] = useState<MockNav | null>(null);
  const [current, setCurrent] = useState<MockQuestion | null>(null);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [calcOpen, setCalcOpen] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittedRef = useRef(false);

  const loadNav = useCallback(async () => {
    const n = await api.get<MockNav>(`/api/mock/${attemptId}/nav`);
    setNav(n);
    if (n.time_limit_seconds) {
      const elapsed = (Date.now() - new Date(n.started_at).getTime()) / 1000;
      setRemaining(n.time_limit_seconds - elapsed);
    }
    return n;
  }, [attemptId]);

  const loadQuestion = useCallback(async (i: number) => {
    const q = await api.get<MockQuestion>(`/api/mock/${attemptId}/question/${i}`);
    setCurrent(q);
    setSelected(q.selected_option);
  }, [attemptId]);

  useEffect(() => {
    (async () => {
      try {
        const n = await loadNav();
        if (n.finished) {
          navigate(`/results/${attemptId}`, { replace: true });
          return;
        }
        await loadQuestion(0);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Could not load this mock exam.');
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId]);

  const submitExam = useCallback(async () => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      await api.post(`/api/mock/${attemptId}/submit`);
    } catch {
      // If it's already submitted (e.g. race with the timeout path) that's fine.
    }
    navigate(`/results/${attemptId}`);
  }, [attemptId, navigate]);

  useEffect(() => {
    if (remaining === null || submittedRef.current) return;
    if (remaining <= 0) {
      submitExam();
      return;
    }
    const t = setTimeout(() => setRemaining((r) => (r !== null ? r - 1 : r)), 1000);
    return () => clearTimeout(t);
  }, [remaining, submitExam]);

  const goTo = async (i: number) => {
    if (!nav || i < 0 || i >= nav.items.length) return;
    setIndex(i);
    setNavOpen(false);
    await loadQuestion(i);
  };

  const selectOption = async (letter: string) => {
    setSelected(letter);
    await api.put(`/api/mock/${attemptId}/answer/${index}`, { selected_option: letter });
    setNav((prev) => prev && {
      ...prev,
      items: prev.items.map((it) => (it.index === index ? { ...it, answered: true } : it)),
    });
  };

  const toggleMark = async () => {
    await api.put(`/api/mock/${attemptId}/mark/${index}`);
    setNav((prev) => prev && {
      ...prev,
      items: prev.items.map((it) => (it.index === index ? { ...it, marked: !it.marked } : it)),
    });
    setCurrent((prev) => prev && { ...prev, marked: !prev.marked });
  };

  const confirmSubmit = () => {
    const unanswered = nav?.items.filter((it) => !it.answered).length ?? 0;
    const msg = unanswered > 0
      ? `You still have ${unanswered} unanswered question${unanswered === 1 ? '' : 's'}. Submit anyway?`
      : 'Submit your exam? You won\'t be able to change any answers after this.';
    if (confirm(msg)) submitExam();
  };

  if (loading) return <Spinner className="w-8 h-8 mt-16" />;
  if (error || !nav || !current) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16">
        <EmptyState
          icon="fa-solid fa-triangle-exclamation"
          title="Couldn't load this mock exam"
          description={error ?? undefined}
          action={<Button onClick={() => navigate('/mock')}>Back to Mock Exam</Button>}
        />
      </div>
    );
  }

  const q = current.question;
  const options: [string, string][] = [
    ['A', q.option_a], ['B', q.option_b], ['C', q.option_c], ['D', q.option_d],
  ];
  const answeredCount = nav.items.filter((it) => it.answered).length;

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 pb-28">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h1 className="font-display font-extrabold text-lg text-ink-900">Mock JAMB CBT</h1>
          <p className="text-xs text-ink-500">{q.subject} &middot; Question {index + 1} of {current.total}</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setCalcOpen(true)} className="w-9 h-9 rounded-full bg-ink-100 text-ink-600 flex items-center justify-center" title="Calculator">
            <i className="fa-solid fa-calculator" />
          </button>
          {remaining !== null && (
            <div className="bg-ink-900 text-white font-mono font-bold px-4 py-2 rounded-full text-sm">
              <i className="fa-regular fa-clock mr-1.5" />
              {fmtTime(remaining)}
            </div>
          )}
        </div>
      </div>

      <Card padding="lg" className="mb-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold text-ink-400">{answeredCount}/{current.total} answered</span>
          <button
            onClick={toggleMark}
            className={`text-xs font-semibold rounded-full px-3 py-1.5 flex items-center gap-1.5 ${
              current.marked ? 'bg-warning-50 text-warning-600' : 'bg-ink-100 text-ink-500'
            }`}
          >
            <i className={current.marked ? 'fa-solid fa-flag' : 'fa-regular fa-flag'} />
            {current.marked ? 'Marked for review' : 'Mark for review'}
          </button>
        </div>

        {q.passage && (
          <Card className="mb-4 bg-brand-50/40 border-brand-100" padding="md">
            {q.passage.title && <h3 className="font-display font-bold text-ink-900 mb-2 text-sm">{q.passage.title}</h3>}
            <p className="text-sm text-ink-600 leading-relaxed whitespace-pre-line">{q.passage.passage_text}</p>
          </Card>
        )}

        <div className="font-semibold text-ink-900 mb-4 leading-relaxed"><QuestionText text={q.question_text} /></div>

        {q.image_url && (
          <img src={q.image_url} alt="Question diagram" className="w-full max-h-72 object-contain rounded-xl border border-ink-100 mb-4 bg-ink-50" />
        )}

        <div className="space-y-2">
          {options.map(([letter, text]) => (
            <label
              key={letter}
              className={`flex items-center gap-3 border rounded-xl px-4 py-3 cursor-pointer transition-colors ${
                selected === letter ? 'border-brand-500 bg-brand-50' : 'border-ink-200 hover:border-brand-300 hover:bg-brand-50/50'
              }`}
            >
              <input type="radio" name="answer" value={letter} checked={selected === letter} onChange={() => selectOption(letter)} className="accent-brand-500 w-4 h-4" />
              <span className="text-sm text-ink-800"><span className="font-bold">{letter}.</span> <MathText text={text} /></span>
            </label>
          ))}
        </div>
      </Card>

      <div className="flex items-center justify-between gap-2">
        <Button variant="outline" onClick={() => goTo(index - 1)} disabled={index === 0}>
          <i className="fa-solid fa-arrow-left mr-1.5" /> Previous
        </Button>
        <Button variant="ghost" onClick={() => setNavOpen(true)}>
          <i className="fa-solid fa-grip mr-1.5" /> All questions
        </Button>
        {index < current.total - 1 ? (
          <Button onClick={() => goTo(index + 1)}>
            Next <i className="fa-solid fa-arrow-right ml-1.5" />
          </Button>
        ) : (
          <Button variant="danger" onClick={confirmSubmit} disabled={submitting}>
            {submitting ? 'Submitting…' : 'End Exam'}
          </Button>
        )}
      </div>

      <div className="fixed bottom-4 right-4 sm:hidden">
        <Button size="sm" variant="danger" onClick={confirmSubmit} disabled={submitting}>
          End Exam
        </Button>
      </div>

      {navOpen && (
        <div className="fixed inset-0 z-30 flex items-end sm:items-center justify-center bg-ink-900/40" onClick={() => setNavOpen(false)}>
          <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-t-2xl sm:rounded-2xl shadow-pop w-full sm:max-w-xl max-h-[80vh] overflow-y-auto p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="font-display font-bold text-ink-900">All questions ({answeredCount}/{current.total} answered)</p>
              <button onClick={() => setNavOpen(false)} className="text-ink-400 hover:text-ink-700">
                <i className="fa-solid fa-xmark text-lg" />
              </button>
            </div>
            <div className="flex items-center gap-4 mb-4 text-xs text-ink-500">
              <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-success-100 border border-success-300 inline-block" /> Answered</span>
              <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-ink-100 border border-ink-200 inline-block" /> Unanswered</span>
              <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-warning-100 border border-warning-400 inline-block" /> Marked</span>
            </div>
            <div className="grid grid-cols-8 sm:grid-cols-10 gap-1.5">
              {nav.items.map((it) => (
                <button
                  key={it.index}
                  onClick={() => goTo(it.index)}
                  className={`aspect-square rounded-lg text-xs font-semibold flex items-center justify-center border transition-colors ${
                    it.index === index ? 'ring-2 ring-brand-500' : ''
                  } ${
                    it.marked
                      ? 'bg-warning-100 text-warning-700 border-warning-400'
                      : it.answered
                      ? 'bg-success-100 text-success-700 border-success-300'
                      : 'bg-ink-100 text-ink-500 border-ink-200'
                  }`}
                >
                  {it.index + 1}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {calcOpen && <Calculator onClose={() => setCalcOpen(false)} />}
    </div>
  );
}
