import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ExamSessionInfo, ExamResults } from '../api/types';
import Card from './ui/Card';
import Spinner from './ui/Spinner';
import ExamBuilder from './ExamBuilder';

/**
 * Running school exams, concierge-style.
 *
 * The builder sets an exam up; everything below is monitoring. Deliberately
 * not self-serve: five exams set up by hand will teach more about what schools
 * actually need than any guessed-at organiser dashboard, and self-serve
 * implies roles, permissions and billing — a lot of machinery to build before
 * the first paying customer.
 */

const API = '/api/exams/manage';

function SessionCard({ session }: { session: ExamSessionInfo }) {
  const { data: results } = useQuery({
    queryKey: ['exam-results', session.id],
    queryFn: () => api.get<ExamResults>(`${API}/sessions/${session.id}/results`),
    enabled: session.registered > 0,
  });

  const link = `${window.location.origin}/exam/${session.code}`;
  const draft = session.status === 'draft';

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
          {session.is_open ? 'Open now' : draft ? 'Draft — not published' : session.status}
        </span>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-600 mb-4">
        <span><strong className="text-ink-900">{session.question_count}</strong> questions</span>
        <span><strong className="text-ink-900">{session.duration_minutes}</strong> min each</span>
        <span><strong className="text-ink-900">{session.registered}</strong> registered</span>
        <span><strong className="text-ink-900">{session.started}</strong> started</span>
        <span><strong className="text-ink-900">{session.submitted}</strong> submitted</span>
      </div>

      {draft ? (
        <p className="text-sm text-warning-700 rounded-xl bg-warning-50 border border-warning-200 p-3">
          This exam has not been published, so the link does not work yet.
        </p>
      ) : (
        <div className="rounded-xl bg-ink-50 border border-ink-100 p-3 mb-4">
          <p className="text-xs text-ink-500 mb-1">Exam link</p>
          <p className="font-mono text-sm text-ink-900 break-all">{link}</p>
        </div>
      )}

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
      <ExamBuilder onCreated={refresh} />
      {(data ?? []).map((s) => <SessionCard key={s.id} session={s} />)}
      {data && data.length === 0 && (
        <p className="text-sm text-ink-500 text-center py-8">No exams yet.</p>
      )}
    </div>
  );
}
