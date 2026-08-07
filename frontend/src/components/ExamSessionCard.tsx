import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type {
  ExamSessionInfo, ExamResults, ExamCandidateIssued, Readiness,
} from '../api/types';
import Card from './ui/Card';
import Button from './ui/Button';
import Field from './ui/Field';

const API = '/api/exams/manage';

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * One exam, with everything the organiser needs to run it.
 *
 * The first version was read-only, which meant a draft that was almost right
 * could only be abandoned, and access codes could only be seen once at
 * creation. Both are unusable in practice: close the tab before printing and
 * fifty students cannot sit the exam.
 *
 * So slips are re-downloadable, drafts can be published or deleted, and the
 * timing can be corrected — but only until someone starts. Once a candidate is
 * mid-paper the rules are frozen, because a school has to be able to trust
 * that the duration cannot move under their pupils.
 */
export default function ExamSessionCard({
  session,
  onChanged,
}: {
  session: ExamSessionInfo;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showSlips, setShowSlips] = useState(false);

  const [opensAt, setOpensAt] = useState(() => toLocalInput(session.opens_at));
  const [closesAt, setClosesAt] = useState(() => toLocalInput(session.closes_at));
  const [duration, setDuration] = useState(session.duration_minutes);

  const draft = session.status === 'draft';
  const locked = session.started > 0;

  const { data: readiness } = useQuery({
    queryKey: ['exam-readiness', session.id],
    queryFn: () => api.get<Readiness>(`${API}/sessions/${session.id}/readiness`),
    enabled: draft,
  });

  const { data: results } = useQuery({
    queryKey: ['exam-results', session.id],
    queryFn: () => api.get<ExamResults>(`${API}/sessions/${session.id}/results`),
    enabled: !draft && session.registered > 0,
  });

  const { data: candidates } = useQuery({
    queryKey: ['exam-candidates', session.id],
    queryFn: () => api.get<ExamCandidateIssued[]>(`${API}/sessions/${session.id}/candidates`),
    enabled: showSlips,
  });

  const run = async (fn: () => Promise<unknown>, fallback: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.message} (HTTP ${e.status})` : fallback);
    } finally {
      setBusy(false);
    }
  };

  const link = `${window.location.origin}/exam/${session.code}`;
  const download = (path: string) => `${import.meta.env.VITE_API_URL || ''}${API}/sessions/${session.id}/${path}`;

  return (
    <Card padding="lg" className="mb-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <p className="font-display font-bold text-ink-900">{session.title}</p>
          <p className="text-sm text-ink-500">{session.organisation}</p>
        </div>
        <span className={`text-xs font-semibold px-2 py-1 rounded-full flex-shrink-0 ${
          session.is_open
            ? 'bg-success-50 text-success-700'
            : draft
              ? 'bg-warning-50 text-warning-700'
              : 'bg-ink-100 text-ink-500'
        }`}>
          {session.is_open ? 'Open now' : draft ? 'Draft' : session.status}
        </span>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-600 mb-2">
        <span><strong className="text-ink-900">{session.question_count}</strong> questions</span>
        <span><strong className="text-ink-900">{session.duration_minutes}</strong> min each</span>
        <span><strong className="text-ink-900">{session.registered}</strong> registered</span>
        <span><strong className="text-ink-900">{session.started}</strong> started</span>
        <span><strong className="text-ink-900">{session.submitted}</strong> submitted</span>
      </div>

      <p className="text-xs text-ink-500 mb-4">
        Opens {new Date(session.opens_at).toLocaleString()} · closes{' '}
        {new Date(session.closes_at).toLocaleString()}
      </p>

      {draft ? (
        <div className="rounded-xl bg-warning-50 border border-warning-200 p-3 mb-4">
          <p className="text-sm text-warning-800 font-semibold mb-1">
            Not published — the link does not work yet.
          </p>
          {readiness && !readiness.ready && (
            <ul className="text-sm text-warning-700 space-y-0.5 mt-1">
              {readiness.problems.map((p) => <li key={p}>• {p}</li>)}
            </ul>
          )}
        </div>
      ) : (
        <div className="rounded-xl bg-ink-50 border border-ink-100 p-3 mb-4">
          <p className="text-xs text-ink-500 mb-1">Exam link</p>
          <p className="font-mono text-sm text-ink-900 break-all">{link}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2 mb-4">
        {draft && (
          <Button
            size="sm"
            onClick={() => run(() => api.post(`${API}/sessions/${session.id}/publish`), 'Could not publish.')}
            disabled={busy || !readiness?.ready}
          >
            Publish
          </Button>
        )}

        {session.registered > 0 && (
          <>
            <Button size="sm" variant="outline" onClick={() => setShowSlips((v) => !v)}>
              {showSlips ? 'Hide slips' : 'Show access codes'}
            </Button>
            <a
              href={download('slips.csv')}
              className="inline-flex items-center rounded-xl border border-ink-200 px-3 py-1.5 text-sm font-semibold text-ink-700 hover:border-brand-300"
            >
              Download slips
            </a>
          </>
        )}

        {!draft && session.submitted > 0 && (
          <a
            href={download('results.csv')}
            className="inline-flex items-center rounded-xl border border-ink-200 px-3 py-1.5 text-sm font-semibold text-ink-700 hover:border-brand-300"
          >
            Download results
          </a>
        )}

        {!locked && (
          <Button size="sm" variant="ghost" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Cancel edit' : 'Edit timing'}
          </Button>
        )}

        {!locked && (
          confirmDelete ? (
            <Button
              size="sm"
              variant="danger"
              onClick={() => run(() => api.delete(`${API}/sessions/${session.id}`), 'Could not delete.')}
              disabled={busy}
            >
              Really delete?
            </Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(true)}>
              Delete
            </Button>
          )
        )}
      </div>

      {locked && (
        <p className="text-xs text-ink-400 mb-4">
          Candidates have started, so this exam can no longer be edited or deleted.
        </p>
      )}

      {/* Edit timing */}
      {editing && !locked && (
        <div className="rounded-xl border border-ink-200 p-3 mb-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Opens" htmlFor={`o-${session.id}`}>
              <input
                id={`o-${session.id}`} type="datetime-local" value={opensAt}
                onChange={(e) => setOpensAt(e.target.value)}
                className="w-full rounded-xl border border-ink-200 px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Closes" htmlFor={`c-${session.id}`}>
              <input
                id={`c-${session.id}`} type="datetime-local" value={closesAt}
                onChange={(e) => setClosesAt(e.target.value)}
                className="w-full rounded-xl border border-ink-200 px-3 py-2 text-sm"
              />
            </Field>
            <Field label="Minutes each" htmlFor={`d-${session.id}`}>
              <input
                id={`d-${session.id}`} type="number" min={5} max={300} value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full rounded-xl border border-ink-200 px-3 py-2 text-sm"
              />
            </Field>
          </div>
          <Button
            size="sm"
            onClick={() => run(() => api.patch(`${API}/sessions/${session.id}`, {
              // Converted from the admin's LOCAL time to UTC, so a 9am exam in
              // Lagos does not become 10am.
              opens_at: new Date(opensAt).toISOString(),
              closes_at: new Date(closesAt).toISOString(),
              duration_minutes: duration,
            }), 'Could not save.')}
            disabled={busy}
          >
            Save changes
          </Button>
        </div>
      )}

      {/* Slips */}
      {showSlips && candidates && (
        <div className="mb-4">
          <p className="text-xs text-ink-500 mb-2">
            Give each candidate their registration number and access code.
          </p>
          <div className="max-h-72 overflow-y-auto rounded-xl border border-ink-200">
            <table className="w-full text-sm">
              <thead className="bg-ink-50 sticky top-0">
                <tr className="text-xs text-ink-500 text-left">
                  <th className="px-2 py-1.5">Registration number</th>
                  <th className="px-2 py-1.5">Name</th>
                  <th className="px-2 py-1.5 text-right">Access code</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
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

      {/* Results */}
      {results && results.candidates.length > 0 && (
        <div>
          <p className="text-sm font-semibold text-ink-700 mb-2">Results</p>
          {results.average_percent !== null && (
            <p className="text-xs text-ink-500 mb-2">
              Average {results.average_percent}% · highest {results.highest} · lowest {results.lowest}
            </p>
          )}
          <div className="max-h-64 overflow-y-auto rounded-xl border border-ink-100">
            <table className="w-full text-sm">
              <tbody>
                {results.candidates.map((c) => (
                  <tr key={c.registration_number} className="border-b border-ink-50 last:border-0">
                    <td className="py-1.5 px-2 font-mono text-xs">{c.registration_number}</td>
                    <td className="py-1.5 px-2 text-ink-600 truncate">{c.full_name || ''}</td>
                    <td className="py-1.5 px-2 text-xs text-ink-400">{c.status}</td>
                    <td className="py-1.5 px-2 text-right font-semibold tabular-nums">
                      {c.status === 'submitted' ? `${c.score}/${c.total}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {results.hardest_questions.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-ink-500 mb-1">Where the class struggled most</p>
              <ul className="text-xs text-ink-600 space-y-1">
                {results.hardest_questions.slice(0, 5).map((q) => (
                  <li key={q.question_id}>
                    <span className="font-semibold text-danger-600">{q.percent_correct}%</span>{' '}
                    {q.topic && <span className="text-ink-400">[{q.topic}]</span>} {q.question_text}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {error && <p className="text-sm text-danger-600 mt-3" role="alert">{error}</p>}
    </Card>
  );
}
