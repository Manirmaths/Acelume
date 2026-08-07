import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import type { ExamPaper, ExamSessionInfo, CandidateResult } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import MathText from '../components/ui/MathText';
import QuestionText from '../components/ui/QuestionText';

const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const;

type Section = { subject: string; start: number; count: number };

/**
 * Split the paper into subject sections.
 *
 * Read off consecutive runs of `subject` rather than grouping by name,
 * because the server already emits the paper subject-blocked (see
 * `exams.subject_blocks`) and a run is exactly what the candidate sees. If a
 * subject ever did appear twice it would show as two sections, which is the
 * honest rendering of a paper that genuinely looks like that.
 */
function sectionsOf(questions: { subject?: string | null }[]): Section[] {
  const out: Section[] = [];
  questions.forEach((q, i) => {
    const subject = q.subject || '';
    const last = out[out.length - 1];
    if (last && last.subject === subject) last.count += 1;
    else out.push({ subject, start: i, count: 1 });
  });
  return out;
}

/**
 * Sitting a school exam. Public route — no account, no login.
 *
 * A candidate arrives with a link, a registration number and an access code.
 * That is the entire credential. Fifty students registering with email inside
 * a fifty-minute slot would eat a quarter of the paper, a third of them have
 * no email address, and every account created would be personal data taken
 * from a minor for no reason.
 *
 * Three things this screen has to get right, because there is no second
 * attempt in an exam hall:
 *
 *   1. **Every answer saves the moment it is tapped.** A phone dying at
 *      question 48 must not cost the first 47.
 *   2. **The clock is the server's.** The countdown here is cosmetic; the
 *      authoritative figure comes from the server on resume.
 *   3. **Resuming is normal, not an error.** Phones die and browsers crash
 *      mid-exam. Re-entering the code must return the same paper with the
 *      same answers and the clock still running.
 */
export default function SitExam() {
  const { code = '' } = useParams();

  const [info, setInfo] = useState<ExamSessionInfo | null>(null);
  const [registration, setRegistration] = useState('');
  const [accessCode, setAccessCode] = useState('');

  const [paper, setPaper] = useState<ExamPaper | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [index, setIndex] = useState(0);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [result, setResult] = useState<CandidateResult | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const submittedRef = useRef(false);

  useEffect(() => {
    api.get<ExamSessionInfo>(`/api/exams/${code}`)
      .then(setInfo)
      .catch(() => setError('No exam found with that link. Check it with your teacher.'));
  }, [code]);

  const creds = { registration_number: registration.trim(), access_code: accessCode.trim().toUpperCase() };

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await api.post<ExamPaper>(`/api/exams/${code}/start`, creds);
      setPaper(data);
      setAnswers(data.answers || {});
      setRemaining(data.seconds_remaining);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start the exam.');
    } finally {
      setBusy(false);
    }
  };

  const submit = useCallback(async () => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    try {
      setResult(await api.post<CandidateResult>(`/api/exams/${code}/submit`, creds));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not submit.');
      submittedRef.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, registration, accessCode]);

  // Cosmetic countdown. The server's figure is authoritative and overrides
  // this on every resume, so a wrong phone clock cannot buy extra time.
  useEffect(() => {
    if (remaining === null || paper === null || result) return;
    if (remaining <= 0) {
      submit();
      return;
    }
    const t = window.setTimeout(() => setRemaining((r) => (r === null ? null : r - 1)), 1000);
    return () => window.clearTimeout(t);
  }, [remaining, paper, result, submit]);

  const choose = async (questionId: number, option: string) => {
    const key = String(questionId);
    const next = { ...answers };
    if (next[key] === option) delete next[key];
    else next[key] = option;
    setAnswers(next);

    // Saved individually and immediately -- see the note at the top.
    setSaving(true);
    try {
      await api.post(`/api/exams/${code}/answer`, {
        ...creds, question_id: questionId, selected_option: next[key] ?? null,
      });
    } catch {
      // A failed save is a bad moment on a school wifi, not a lost exam. The
      // answer stays on screen and the next tap retries.
    } finally {
      setSaving(false);
    }
  };

  const sections = useMemo(() => sectionsOf(paper?.questions ?? []), [paper]);
  const section = useMemo(
    () => sections.find((s) => index >= s.start && index < s.start + s.count),
    [sections, index]
  );

  // ---------------------------------------------------------------- done

  if (result) {
    return (
      <div className="max-w-lg mx-auto px-4 py-16 text-center">
        <div className="w-16 h-16 rounded-full bg-success-50 text-success-600 flex items-center justify-center mx-auto mb-4 text-2xl">
          <i className="fa-solid fa-check" />
        </div>
        <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-2">Submitted</h1>
        <p className="text-ink-500 mb-6">
          {result.registration_number}
          {result.full_name && ` · ${result.full_name}`}
        </p>
        {result.answers_shown ? (
          <Card padding="lg">
            <p className="font-display font-extrabold text-4xl text-ink-900">
              {result.score}<span className="text-ink-400 text-2xl">/{result.total}</span>
            </p>
            <p className="text-ink-500 mt-1">{result.percent}%</p>
          </Card>
        ) : (
          <p className="text-sm text-ink-500">
            Your answers have been recorded. Your school will share the results.
          </p>
        )}
      </div>
    );
  }

  // ------------------------------------------------------------ sign in

  if (!paper) {
    return (
      <div className="max-w-md mx-auto px-4 py-12">
        <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">
          {info?.title ?? 'Exam'}
        </h1>
        <p className="text-ink-500 mb-6">{info?.organisation}</p>

        <Card padding="lg">
          <p className="text-sm text-ink-600 mb-4">
            Enter the registration number and access code on your slip.
          </p>

          <label className="block text-sm font-semibold text-ink-700 mb-1" htmlFor="reg">
            Registration number
          </label>
          <input
            id="reg"
            value={registration}
            onChange={(e) => setRegistration(e.target.value)}
            className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 mb-3 focus:outline-none focus:ring-2 focus:ring-brand-200"
          />

          <label className="block text-sm font-semibold text-ink-700 mb-1" htmlFor="ac">
            Access code
          </label>
          <input
            id="ac"
            value={accessCode}
            onChange={(e) => setAccessCode(e.target.value.toUpperCase())}
            maxLength={12}
            className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 mb-4 font-mono tracking-widest uppercase focus:outline-none focus:ring-2 focus:ring-brand-200"
          />

          <Button
            fullWidth
            size="lg"
            onClick={start}
            disabled={busy || !registration.trim() || !accessCode.trim()}
          >
            {busy ? 'Starting…' : 'Start exam'}
          </Button>

          {error && <p className="text-sm text-danger-600 mt-3" role="alert">{error}</p>}
        </Card>

        {info && (
          <p className="text-xs text-ink-400 mt-4 text-center">
            {info.question_count} questions · {info.duration_minutes} minutes
          </p>
        )}
      </div>
    );
  }

  // -------------------------------------------------------------- paper

  const question = paper.questions[index];
  const answered = Object.keys(answers).length;
  const minutes = Math.floor((remaining ?? 0) / 60);
  const seconds = (remaining ?? 0) % 60;
  const urgent = (remaining ?? 0) <= 300;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 pb-28">
      {/*
        Exam-paper letterhead. A candidate glancing down mid-paper should be
        able to confirm they are sitting the right exam under the right number
        without leaving the screen -- and an invigilator walking the room can
        check a screen against the slip in one look.
      */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <p className="font-display font-extrabold text-ink-900 truncate">{paper.title}</p>
          <p className="text-xs text-ink-500 truncate">{paper.organisation}</p>
          <p className="text-sm text-ink-700 mt-1.5 truncate">
            {paper.full_name && <span className="font-semibold">{paper.full_name} · </span>}
            <span className="font-mono">{paper.registration_number}</span>
          </p>
        </div>
        <div
          className={`font-mono font-bold tabular-nums text-lg px-3 py-1.5 rounded-xl shrink-0 ${
            urgent ? 'bg-danger-50 text-danger-600' : 'bg-ink-100 text-ink-700'
          }`}
          role="timer"
        >
          {minutes}:{String(seconds).padStart(2, '0')}
        </div>
      </div>

      {/*
        Section heading. Numbering is per subject, because that is the unit the
        candidate budgets time in -- "12 of 20 in Mathematics" tells them
        something "32 of 60" does not.
      */}
      {section && section.subject && (
        <div className="border-l-4 border-brand-500 pl-3 mb-3">
          <p className="font-display font-bold text-ink-900">{section.subject}</p>
          <p className="text-xs text-ink-500">
            Question {index - section.start + 1} of {section.count}
          </p>
        </div>
      )}

      <p className="text-xs text-ink-400 mb-3">
        {(!section || !section.subject) && `Question ${index + 1} of ${paper.questions.length} · `}
        {answered} of {paper.questions.length} answered
        {saving && <span className="ml-2 text-ink-300">saving…</span>}
      </p>

      <Card padding="lg" className="mb-4">
        <div className="font-semibold text-ink-900 mb-4 leading-relaxed">
          <QuestionText text={question.question_text} />
        </div>
        {question.image_url && (
          <img
            src={question.image_url}
            alt=""
            className="w-full max-h-64 object-contain rounded-xl border border-ink-100 mb-4"
          />
        )}

        <div className="space-y-2">
          {OPTION_KEYS.map((key) => {
            const text = {
              A: question.option_a, B: question.option_b,
              C: question.option_c, D: question.option_d,
            }[key];
            const picked = answers[String(question.id)] === key;
            return (
              <button
                key={key}
                onClick={() => choose(question.id, key)}
                className={`w-full text-left text-sm rounded-xl border px-3.5 py-3 transition-colors ${
                  picked
                    ? 'border-brand-500 bg-brand-50 text-ink-900'
                    : 'border-ink-200 hover:border-brand-300 hover:bg-brand-50/40'
                }`}
              >
                <span className="font-bold mr-2">{key}.</span>
                <MathText text={text} />
              </button>
            );
          })}
        </div>
      </Card>

      {/*
        Question grid — an exam needs free navigation, not a forced march.
        Split by subject so "how much Maths have I left?" is answerable at a
        glance, and numbered within the subject to match the heading above.
      */}
      <div className="space-y-4 mb-6">
        {sections.map((s) => (
          <div key={`${s.subject}-${s.start}`}>
            {s.subject && (
              <p className="text-xs font-semibold text-ink-500 mb-1.5">
                {s.subject}
                <span className="font-normal text-ink-400">
                  {' · '}
                  {paper.questions
                    .slice(s.start, s.start + s.count)
                    .filter((q) => answers[String(q.id)]).length}
                  /{s.count} answered
                </span>
              </p>
            )}
            <div className="flex flex-wrap gap-1.5">
              {paper.questions.slice(s.start, s.start + s.count).map((q, i) => {
                const position = s.start + i;
                return (
                  <button
                    key={q.id}
                    onClick={() => setIndex(position)}
                    aria-label={`${s.subject || 'Question'} ${i + 1}`}
                    className={`w-9 h-9 rounded-lg text-xs font-semibold border ${
                      position === index
                        ? 'border-brand-500 bg-brand-500 text-white'
                        : answers[String(q.id)]
                          ? 'border-brand-200 bg-brand-50 text-brand-700'
                          : 'border-ink-200 text-ink-400'
                    }`}
                  >
                    {i + 1}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="fixed bottom-0 inset-x-0 bg-white border-t border-ink-100 px-4 py-3">
        <div className="max-w-2xl mx-auto flex gap-2">
          <Button variant="outline" onClick={() => setIndex((i) => Math.max(0, i - 1))} disabled={index === 0}>
            Back
          </Button>
          {index < paper.questions.length - 1 ? (
            <Button fullWidth onClick={() => setIndex((i) => i + 1)}>Next</Button>
          ) : (
            <Button fullWidth variant="secondary" onClick={submit}>
              Submit exam
            </Button>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-danger-600 mt-3" role="alert">{error}</p>}
    </div>
  );
}
