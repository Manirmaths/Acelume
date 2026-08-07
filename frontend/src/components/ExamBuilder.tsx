import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type {
  ExamSessionInfo, SubjectAvailability, Readiness, ExamCandidateIssued, ImportReport,
} from '../api/types';
import Card from './ui/Card';
import Button from './ui/Button';
import Field, { TextInput } from './ui/Field';

const API = '/api/exams/manage';

/**
 * Setting up a school exam, as a wizard with a review gate.
 *
 * The first version created a session the moment you filled in a form, and a
 * session became live as soon as it had one candidate. That is the wrong shape
 * for an exam: half-configured is a much worse failure than refusing to
 * publish, because nobody notices until fifty pupils are sitting in front of
 * it. So nothing is usable — no link, no codes — until Publish, and Publish
 * re-checks everything on the server.
 *
 * Every field is labelled rather than relying on placeholders, which vanish
 * the moment you type. A row of boxes reading "3", "20" and "60" with no
 * labels is how someone sets a sixty-minute exam to three minutes.
 */

/**
 * Say what actually went wrong.
 *
 * "Could not create the exam." on its own is useless precisely when it
 * matters -- it cannot distinguish a backend that has not deployed yet from a
 * server error from a validation problem, and each needs a different
 * response. The server's own message is almost always the useful one, so it
 * leads; the status code follows for the cases where it is not.
 */
function describe(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) {
    return `${fallback} The API could not be reached — it may still be starting up.`;
  }
  if (error.status === 404) {
    return `${fallback} The API does not have this endpoint yet — the backend is probably still deploying.`;
  }
  if (error.status >= 500) {
    return `${fallback} The server errored (${error.status}). Check the API logs. ${error.message}`;
  }
  return `${error.message} (HTTP ${error.status})`;
}

/**
 * `datetime-local` wants "YYYY-MM-DDTHH:mm" in LOCAL time, with no timezone.
 * Everything is converted to UTC before it reaches the API — an admin in
 * Lagos setting 9am must not produce a 10am exam.
 */
function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Sensible defaults: opens tomorrow morning, closes a week later. A default of
// "now" would let a half-checked exam be sat the moment it is published.
const defaultOpensAt = (() => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(8, 0, 0, 0);
  return toLocalInput(d);
})();

const defaultClosesAt = (() => {
  const d = new Date();
  d.setDate(d.getDate() + 8);
  d.setHours(17, 0, 0, 0);
  return toLocalInput(d);
})();

interface SubjectRow {
  subject: string;
  count: number;
}

export default function ExamBuilder({ onCreated }: { onCreated: () => void }) {
  const [step, setStep] = useState(1);

  // Step 1 — what and when
  const [title, setTitle] = useState('');
  const [organisation, setOrganisation] = useState('');
  const [duration, setDuration] = useState(60);
  const [opensAt, setOpensAt] = useState(defaultOpensAt);
  const [closesAt, setClosesAt] = useState(defaultClosesAt);
  const [showAnswers, setShowAnswers] = useState(false);

  // Step 2 — questions
  const [source, setSource] = useState<'bank' | 'upload'>('bank');
  const [rows, setRows] = useState<SubjectRow[]>([{ subject: 'Mathematics', count: 20 }]);

  // Step 3 — candidates
  const [candidateCount, setCandidateCount] = useState(50);
  const [namesText, setNamesText] = useState('');

  // Created session
  const [session, setSession] = useState<ExamSessionInfo | null>(null);
  const [issued, setIssued] = useState<ExamCandidateIssued[] | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: availability } = useQuery({
    queryKey: ['exam-subject-availability'],
    queryFn: () => api.get<SubjectAvailability[]>(`${API}/subjects`),
  });

  const availableFor = (subject: string) =>
    availability?.find((a) => a.subject === subject)?.available ?? 0;

  const totalQuestions = rows.reduce((sum, r) => sum + (r.count || 0), 0);

  // ------------------------------------------------------------ actions

  const createDraft = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<ExamSessionInfo>(`${API}/sessions`, {
        title, organisation,
        blueprint: source === 'bank' ? rows : [],
        duration_minutes: duration,
        source,
        // Sent as UTC. The inputs are the ADMIN'S local time, so converting
        // here is what stops a 9am exam in Lagos opening at 10am.
        opens_at: new Date(opensAt).toISOString(),
        closes_at: new Date(closesAt).toISOString(),
        show_answers: showAnswers,
      });
      setSession(created);
      setStep(3);
    } catch (e) {
      setError(describe(e, 'Could not create the exam.'));
    } finally {
      setBusy(false);
    }
  };

  const uploadQuestions = async (file: File) => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(
        `${import.meta.env.VITE_API_URL || ''}${API}/sessions/${session.id}/questions`,
        { method: 'POST', credentials: 'include', body: form },
      );
      setReport(await res.json());
    } catch {
      setError('Upload failed.');
    } finally {
      setBusy(false);
    }
  };

  const addCandidates = async () => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const named = namesText
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [name, reference] = line.split(',');
          return { full_name: name.trim(), school_reference: (reference || '').trim() || null };
        });

      setIssued(await api.post<ExamCandidateIssued[]>(
        `${API}/sessions/${session.id}/candidates`,
        { count: named.length ? 0 : candidateCount, candidates: named },
      ));
      setStep(4);
      await refreshReadiness();
    } catch (e) {
      setError(describe(e, 'Could not add candidates.'));
    } finally {
      setBusy(false);
    }
  };

  const refreshReadiness = async () => {
    if (!session) return;
    setReadiness(await api.get<Readiness>(`${API}/sessions/${session.id}/readiness`));
  };

  const publish = async () => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await api.post<ExamSessionInfo>(`${API}/sessions/${session.id}/publish`));
      setStep(5);
      onCreated();
    } catch (e) {
      setError(describe(e, 'Could not publish.'));
    } finally {
      setBusy(false);
    }
  };

  // ------------------------------------------------------------- render

  const Steps = () => (
    <div className="flex items-center gap-1 mb-6 text-xs">
      {['Details', 'Questions', 'Candidates', 'Review', 'Done'].map((label, i) => (
        <div key={label} className="flex items-center">
          <span
            className={`px-2.5 py-1 rounded-full font-semibold ${
              step === i + 1
                ? 'bg-brand-500 text-white'
                : step > i + 1
                  ? 'bg-brand-50 text-brand-700'
                  : 'bg-ink-100 text-ink-400'
            }`}
          >
            {i + 1}. {label}
          </span>
          {i < 4 && <i className="fa-solid fa-chevron-right text-ink-300 mx-1 text-[10px]" />}
        </div>
      ))}
    </div>
  );

  return (
    <Card padding="lg" className="mb-6">
      <h3 className="font-display font-bold text-ink-900 mb-4">Set up an exam</h3>
      <Steps />

      {/* 1 — details */}
      {step === 1 && (
        <div className="space-y-4">
          <Field label="Exam title" hint="What the candidates will see, e.g. 'Entrance Exam 2026'." htmlFor="ex-title">
            <TextInput id="ex-title" value={title} onChange={setTitle} placeholder="Entrance Exam 2026" />
          </Field>

          <Field label="School or organisation" htmlFor="ex-org">
            <TextInput id="ex-org" value={organisation} onChange={setOrganisation} placeholder="Federal Government College, Sokoto" />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Time allowed per candidate"
              hint="In MINUTES. Each candidate's clock starts when they begin, not at a fixed time."
              htmlFor="ex-dur"
            >
              <TextInput id="ex-dur" type="number" min={5} max={300} value={duration} onChange={(v) => setDuration(Number(v))} />
            </Field>

            <Field
              label="Exam opens"
              hint="Your local time. Candidates cannot start before this."
              htmlFor="ex-opens"
            >
              <input
                id="ex-opens" type="datetime-local" value={opensAt}
                onChange={(e) => setOpensAt(e.target.value)}
                className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </Field>

            <Field
              label="Exam closes"
              hint="After this nobody can start. Useful when a school rotates classes through one computer lab."
              htmlFor="ex-closes"
            >
              <input
                id="ex-closes" type="datetime-local" value={closesAt}
                onChange={(e) => setClosesAt(e.target.value)}
                className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </Field>
          </div>

          <label className="flex items-start gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={showAnswers}
              onChange={(e) => setShowAnswers(e.target.checked)}
              className="mt-1"
            />
            <span>
              Show candidates their score immediately
              <span className="block text-xs text-ink-400">
                Leave off if the school runs the same paper across two days — otherwise the
                first group can brief the second.
              </span>
            </span>
          </label>

          <Button onClick={() => setStep(2)} disabled={!title.trim() || !organisation.trim()}>
            Next: questions
          </Button>
        </div>
      )}

      {/* 2 — questions */}
      {step === 2 && (
        <div className="space-y-4">
          <Field label="Where do the questions come from?">
            <div className="grid gap-2 sm:grid-cols-2">
              {([
                ['bank', 'Acelume question bank', 'Pick subjects and how many of each. Questions are sampled fresh for this exam.'],
                ['upload', "The school's own questions", 'Upload their spreadsheet. Replaces the bank entirely for this paper.'],
              ] as const).map(([key, label, hint]) => (
                <button
                  key={key}
                  onClick={() => setSource(key)}
                  className={`text-left rounded-xl border p-3 ${
                    source === key ? 'border-brand-500 bg-brand-50' : 'border-ink-200 hover:border-brand-300'
                  }`}
                >
                  <span className="block text-sm font-semibold text-ink-900">{label}</span>
                  <span className="block text-xs text-ink-500 mt-0.5">{hint}</span>
                </button>
              ))}
            </div>
          </Field>

          {source === 'bank' && (
            <div>
              <p className="text-sm font-semibold text-ink-800 mb-1">Subjects and question counts</p>
              <p className="text-xs text-ink-400 mb-3">
                Add a row per subject. For an entrance exam that might be three subjects at
                20 questions each.
              </p>

              <div className="space-y-2">
                {rows.map((row, i) => {
                  const have = availableFor(row.subject);
                  const short = row.count > have;
                  return (
                    <div key={i} className="flex items-end gap-2">
                      <div className="flex-1">
                        <label className="block text-xs text-ink-500 mb-1">Subject</label>
                        <select
                          value={row.subject}
                          onChange={(e) => {
                            const next = [...rows];
                            next[i] = { ...row, subject: e.target.value };
                            setRows(next);
                          }}
                          className="w-full rounded-xl border border-ink-200 px-3 py-2.5 text-sm"
                        >
                          {(availability ?? []).map((a) => (
                            <option key={a.subject} value={a.subject}>
                              {a.subject} ({a.available} available)
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="w-32">
                        <label className="block text-xs text-ink-500 mb-1">Questions</label>
                        <input
                          type="number" min={1} max={have || 200} value={row.count}
                          onChange={(e) => {
                            const next = [...rows];
                            next[i] = { ...row, count: Number(e.target.value) };
                            setRows(next);
                          }}
                          className={`w-full rounded-xl border px-3 py-2.5 text-sm ${
                            short ? 'border-danger-400 bg-danger-50' : 'border-ink-200'
                          }`}
                        />
                      </div>
                      <button
                        onClick={() => setRows(rows.filter((_, j) => j !== i))}
                        disabled={rows.length === 1}
                        className="px-3 py-2.5 text-ink-400 hover:text-danger-600 disabled:opacity-30"
                        aria-label="Remove subject"
                      >
                        <i className="fa-solid fa-trash" />
                      </button>
                    </div>
                  );
                })}
              </div>

              {rows.some((r) => r.count > availableFor(r.subject)) && (
                <p className="text-xs text-danger-600 mt-2">
                  One or more subjects ask for more questions than the bank holds. Reduce the
                  count, or the exam cannot be published.
                </p>
              )}

              <button
                onClick={() => setRows([...rows, { subject: 'English', count: 20 }])}
                className="mt-3 text-sm font-semibold text-brand-600 hover:text-brand-700"
              >
                + Add another subject
              </button>

              <p className="text-sm text-ink-600 mt-3">
                Total: <strong className="text-ink-900">{totalQuestions}</strong> questions
                across <strong className="text-ink-900">{rows.length}</strong> subject
                {rows.length === 1 ? '' : 's'}, {duration} minutes.
              </p>
            </div>
          )}

          {source === 'upload' && (
            <p className="text-sm text-ink-500">
              You'll upload the spreadsheet on the next screen, once the exam exists.
              <a
                href={`${import.meta.env.VITE_API_URL || ''}${API}/template.csv`}
                className="ml-2 font-semibold text-brand-600 hover:text-brand-700"
              >
                Download the template
              </a>
            </p>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
            <Button onClick={createDraft} disabled={busy || (source === 'bank' && totalQuestions === 0)}>
              {busy ? 'Creating…' : 'Next: candidates'}
            </Button>
          </div>
        </div>
      )}

      {/* 3 — candidates */}
      {step === 3 && session && (
        <div className="space-y-4">
          {source === 'upload' && (
            <Field
              label="Upload the school's questions"
              hint="An .xlsx file. Every bad row is reported with its number so the school can fix them all at once."
            >
              <label className="inline-flex items-center gap-2 rounded-xl border border-ink-200 px-3 py-2.5 text-sm cursor-pointer hover:border-brand-300">
                <i className="fa-solid fa-file-excel text-success-600" />
                Choose file
                <input
                  type="file" accept=".xlsx" className="hidden"
                  onChange={(e) => e.target.files?.[0] && uploadQuestions(e.target.files[0])}
                />
              </label>
            </Field>
          )}

          {report && (
            <div className="text-sm">
              {report.fatal ? (
                <p className="text-danger-600">{report.fatal}</p>
              ) : (
                <>
                  <p className="text-success-700 font-semibold">{report.imported} questions imported.</p>
                  {report.errors.length > 0 && (
                    <div className="mt-2 rounded-xl bg-warning-50 border border-warning-200 p-3">
                      <p className="text-xs font-semibold text-warning-700 mb-1">
                        {report.errors.length} row{report.errors.length === 1 ? '' : 's'} skipped —
                        send these back to the school:
                      </p>
                      <ul className="text-xs text-ink-600 space-y-0.5">
                        {report.errors.slice(0, 15).map((e) => (
                          <li key={e.row}>Row {e.row}: {e.problem}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          <Field
            label="How many candidates?"
            hint="Registration numbers are generated automatically — one letter, seven digits, two letters. Each is unique across every exam ever run."
            htmlFor="ex-count"
          >
            <TextInput id="ex-count" type="number" min={1} max={500} value={candidateCount} onChange={(v) => setCandidateCount(Number(v))} />
          </Field>

          <Field
            label="Or paste a name list (optional)"
            hint="One per line: name, then optionally a comma and the school's own reference. If you paste names, the number above is ignored."
          >
            <textarea
              value={namesText}
              onChange={(e) => setNamesText(e.target.value)}
              rows={4}
              placeholder={'Amina Bello, JSS3/014\nChidi Okeke, JSS3/015'}
              className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm font-mono"
            />
          </Field>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
            <Button onClick={addCandidates} disabled={busy}>
              {busy ? 'Adding…' : 'Next: review'}
            </Button>
          </div>
        </div>
      )}

      {/* 4 — review */}
      {step === 4 && session && (
        <div className="space-y-4">
          <p className="text-sm text-ink-600">
            Check everything before publishing. Nothing works until you do — the link is dead
            and the codes cannot be used.
          </p>

          <div className="rounded-xl border border-ink-100 divide-y divide-ink-100">
            {[
              ['Exam', session.title],
              ['School', session.organisation],
              ['Questions', `${readiness?.questions ?? session.question_count}`],
              ['Subjects', source === 'upload' ? "School's own upload" : `${readiness?.subjects ?? rows.length}`],
              ['Time allowed', `${session.duration_minutes} minutes per candidate`],
              ['Opens', new Date(session.opens_at).toLocaleString()],
              ['Closes', new Date(session.closes_at).toLocaleString()],
              ['Candidates', `${readiness?.candidates ?? 0}`],
              ['Answers shown', session.show_answers ? 'Yes' : 'No'],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 px-3 py-2 text-sm">
                <span className="text-ink-500">{label}</span>
                <span className="font-semibold text-ink-900 text-right">{value}</span>
              </div>
            ))}
          </div>

          {readiness && !readiness.ready && (
            <div className="rounded-xl bg-danger-50 border border-danger-200 p-3">
              <p className="text-sm font-semibold text-danger-700 mb-1">Not ready yet:</p>
              <ul className="text-sm text-danger-600 space-y-0.5">
                {readiness.problems.map((p) => <li key={p}>• {p}</li>)}
              </ul>
            </div>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(3)}>Back</Button>
            <Button variant="secondary" onClick={publish} disabled={busy || !readiness?.ready}>
              {busy ? 'Publishing…' : 'Publish exam'}
            </Button>
          </div>
        </div>
      )}

      {/* 5 — done */}
      {step === 5 && session && (
        <div className="space-y-4">
          <div className="rounded-xl bg-success-50 border border-success-200 p-3">
            <p className="text-sm font-semibold text-success-700">
              Published. Give the school the link and the slips below.
            </p>
          </div>

          <Field label="Exam link">
            <p className="font-mono text-sm text-ink-900 break-all rounded-xl bg-ink-50 border border-ink-100 p-3">
              {window.location.origin}/exam/{session.code}
            </p>
          </Field>

          {issued && (
            <div>
              <p className="text-sm font-semibold text-ink-800 mb-1">
                Candidate slips — print these now
              </p>
              <p className="text-xs text-danger-600 mb-2">
                Access codes are never shown again.
              </p>
              <div className="max-h-80 overflow-y-auto rounded-xl border border-ink-200">
                <table className="w-full text-sm">
                  <thead className="bg-ink-50 sticky top-0">
                    <tr className="text-xs text-ink-500 text-left">
                      <th className="px-2 py-1.5">Registration number</th>
                      <th className="px-2 py-1.5">Name</th>
                      <th className="px-2 py-1.5 text-right">Access code</th>
                    </tr>
                  </thead>
                  <tbody>
                    {issued.map((c) => (
                      <tr key={c.registration_number} className="border-t border-ink-100">
                        <td className="px-2 py-1.5 font-mono">{c.registration_number}</td>
                        <td className="px-2 py-1.5 text-ink-600">
                          {c.full_name || <span className="text-ink-300">—</span>}
                          {c.school_reference && (
                            <span className="text-ink-400 text-xs ml-1">({c.school_reference})</span>
                          )}
                        </td>
                        <td className="px-2 py-1.5 font-mono font-bold text-right tracking-widest">
                          {c.access_code}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <Button variant="outline" onClick={() => window.location.reload()}>
            Set up another exam
          </Button>
        </div>
      )}

      {error && <p className="text-sm text-danger-600 mt-3" role="alert">{error}</p>}
    </Card>
  );
}
