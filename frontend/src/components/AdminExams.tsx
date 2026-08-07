import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ExamSessionInfo } from '../api/types';
import Spinner from './ui/Spinner';
import ExamBuilder from './ExamBuilder';
import ExamSessionCard from './ExamSessionCard';

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
      {(data ?? []).map((s) => <ExamSessionCard key={s.id} session={s} onChanged={refresh} />)}
      {data && data.length === 0 && (
        <p className="text-sm text-ink-500 text-center py-8">No exams yet.</p>
      )}
    </div>
  );
}
