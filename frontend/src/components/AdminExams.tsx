import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { ExamSessionInfo, ExamResults, ExamCandidateIssued, ImportReport } from '../api/types';
import Card from './ui/Card';
import Button from './ui/Button';
import Spinner from './ui/Spinner';

/**
 * Running a school's exam, concierge-style.
 *
 * You create the session, load the questions and hand the school a sheet of
 * codes. Deliberately not self-serve: five exams set up by hand will teach
 * more about what schools actually need than any guessed-at organiser
 * dashboard, and the role system, permissions and billing that self-serve
 * implies are a lot of machinery to build before the first customer.
 */

const API = '/api/exams/manage';

function CreateSession({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState('');
  const [organisation, setOrganisation] = useState('');
  const [subject, setSubject] = useState('Mathematics');
  const [count, setCount] = useState(40);
  const [duration, setDuration] = useState(50);
  const [days, setDays] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const opens = new Date();
      const closes = new Date(Date.now() + days * 86400000);
      await api.post(`${API}/sessions`, {
        title, organisation,
        blueprint: [{ subject, count }],
        duration_minutes: duration,
        source: 'bank',
        opens_at: opens.toISOString(),
        closes_at: closes.toISOString(),
        show_answers: false,
      });
      setTitle('');
      onCreated();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not create the session.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card padding="lg" className="mb-6">
      <h3 className="font-display font-bold text-ink-900 mb-3">New exam</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <input
          value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder="Title, e.g. Second Term Mock"
          className="rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm"
        />
        <input
          value={organisation} onChange={(e) => setOrganisation(e.target.value)}
          placeholder="School name"
          className="rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm"
        />
        <input
          value={subject} onChange={(e) => setSubject(e.target.value)}
          placeholder="Subject"
          className="rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm"
        />
        <input
          type="number" value={count} onChange={(e) => setCount(Number(e.target.value))}
          placeholder="Questions"
          className="rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm"
        />
        <input
          type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))}
          placeholder="Minutes"
          className="rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm"
        />
        <input
          type="number" value={days} onChange={(e) => setDays(Number(e.target.value))}
          placeholder="Open for (days)"
          className="rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm"
        />
      </div>
      <Button className="mt-3" onClick={create} disabled={busy || !title.trim() || !organisation.trim()}>
        {busy ? 'Creating…' : 'Create'}
      </Button>
      {error && <p className="text-sm text-danger-600 mt-2">{error}</p>}
      <p className="text-xs text-ink-400 mt-3">
        Uses Acelume's question bank. To use the school's own questions, upload their
        spreadsheet after creating — that replaces the bank questions entirely.
      </p>
    </Card>
  );
}

function SessionDetail({ session, onChanged }: { session: ExamSessionInfo; onChanged: () => void }) {
  const [registrations, setRegistrations] = useState('');
  const [issued, setIssued] = useState<ExamCandidateIssued[] | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: results } = useQuery({
    queryKey: ['exam-results', session.id],
    queryFn: () => api.get<ExamResults>(`${API}/sessions/${session.id}/results`),
    enabled: session.registered > 0,
  });

  const addCandidates = async () => {
    const rows = registrations
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [reg, ...rest] = line.split(',');
        return { registration_number: reg.trim(), full_name: rest.join(',').trim() || null };
      });
    if (!rows.length) return;

    setBusy(true);
    setError(null);
    try {
      setIssued(await api.post<ExamCandidateIssued[]>(`${API}/sessions/${session.id}/candidates`, rows));
      setRegistrations('');
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not register candidates.');
    } finally {
      setBusy(false);
    }
  };

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${import.meta.env.VITE_API_URL || ''}${API}/sessions/${session.id}/questions`, {
        method: 'POST', credentials: 'include', body: form,
      });
      setReport(await res.json());
      onChanged();
    } catch {
      setError('Upload failed.');
    } finally {
      setBusy(false);
    }
  };

  const link = `${window.location.origin}/exam/${session.code}`;

  return (
    <Card padding="lg" className="mb-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <p className="font-display font-bold text-ink-900">{session.title}</p>
          <p className="text-sm text-ink-500">{session.organisation}</p>
        </div>
        <span className={`text-xs font-semibold px-2 py-1 rounded-full flex-shrink-0 ${
          session.is_open ? 'bg-success-50 text-success-700' : 'bg-ink-100 text-ink-500'
        }`}>
          {session.is_open ? 'Open' : session.status}
        </span>
      </div>

      <div className="flex flex-wrap gap-4 text-sm text-ink-600 mb-4">
        <span><strong className="text-ink-900">{session.question_count}</strong> questions</span>
        <span><strong className="text-ink-900">{session.duration_minutes}</strong> min</span>
        <span><strong className="text-ink-900">{session.registered}</strong> registered</span>
        <span><strong className="text-ink-900">{session.started}</strong> started</span>
        <span><strong className="text-ink-900">{session.submitted}</strong> submitted</span>
      </div>

      <div className="rounded-xl bg-ink-50 border border-ink-100 p-3 mb-4">
        <p className="text-xs text-ink-500 mb-1">Give the school this link</p>
        <p className="font-mono text-sm text-ink-900 break-all">{link}</p>
      </div>

      {/* Questions */}
      <div className="mb-4">
        <p className="text-sm font-semibold text-ink-700 mb-2">School's own questions</p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-2 rounded-xl border border-ink-200 px-3 py-2 text-sm cursor-pointer hover:border-brand-300">
            <i className="fa-solid fa-file-excel text-success-600" />
            Upload spreadsheet
            <input
              type="file" accept=".xlsx" className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
          </label>
          <a
            href={`${import.meta.env.VITE_API_URL || ''}${API}/template.csv`}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700"
          >
            Download template
          </a>
        </div>

        {report && (
          <div className="mt-3 text-sm">
            {report.fatal ? (
              <p className="text-danger-600">{report.fatal}</p>
            ) : (
              <>
                <p className="text-success-700 font-semibold">{report.imported} questions imported.</p>
                {report.errors.length > 0 && (
                  <div className="mt-2 rounded-xl bg-warning-50 border border-warning-200 p-3">
                    <p className="text-xs font-semibold text-warning-700 mb-1">
                      {report.errors.length} row{report.errors.length === 1 ? '' : 's'} skipped —
                      send these back to the school to fix:
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
      </div>

      {/* Candidates */}
      <div className="mb-4">
        <p className="text-sm font-semibold text-ink-700 mb-1">Register candidates</p>
        <p className="text-xs text-ink-400 mb-2">
          One per line: registration number, then optionally a comma and their name.
        </p>
        <textarea
          value={registrations}
          onChange={(e) => setRegistrations(e.target.value)}
          rows={4}
          placeholder={'001, Amina Bello\n002, Chidi Okeke\n003'}
          className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm font-mono"
        />
        <Button className="mt-2" onClick={addCandidates} disabled={busy || !registrations.trim()}>
          Issue access codes
        </Button>
      </div>

      {issued && (
        <div className="rounded-xl border border-brand-200 bg-brand-50/50 p-3 mb-4">
          <p className="text-xs font-semibold text-brand-700 mb-2">
            Print this now — access codes are never shown again.
          </p>
          <table className="w-full text-sm">
            <tbody>
              {issued.map((c) => (
                <tr key={c.registration_number} className="border-b border-brand-100 last:border-0">
                  <td className="py-1 font-mono">{c.registration_number}</td>
                  <td className="py-1 text-ink-600">{c.full_name || ''}</td>
                  <td className="py-1 font-mono font-bold text-right tracking-widest">{c.access_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Results */}
      {results && results.candidates.length > 0 && (
        <div>
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-sm font-semibold text-ink-700">Results</p>
            <a
              href={`${import.meta.env.VITE_API_URL || ''}${API}/sessions/${session.id}/results.csv`}
              className="text-xs font-semibold text-brand-600 hover:text-brand-700"
            >
              Download CSV
            </a>
          </div>

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
              {/* What turns a mark sheet into something a teacher can use:
                  the questions the class as a whole failed. */}
              <p className="text-xs font-semibold text-ink-500 mb-1">
                Where the class struggled most
              </p>
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

      {error && <p className="text-sm text-danger-600 mt-2">{error}</p>}
    </Card>
  );
}

export default function AdminExams() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['exam-sessions'],
    queryFn: () => api.get<ExamSessionInfo[]>(`${API}/sessions`),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['exam-sessions'] });
    queryClient.invalidateQueries({ queryKey: ['exam-results'] });
  };

  if (isLoading) return <Spinner className="w-8 h-8 mt-12" />;

  return (
    <div>
      <CreateSession onCreated={refresh} />
      {(data ?? []).map((s) => (
        <SessionDetail key={s.id} session={s} onChanged={refresh} />
      ))}
      {data && data.length === 0 && (
        <p className="text-sm text-ink-500 text-center py-8">No exams yet.</p>
      )}
    </div>
  );
}
