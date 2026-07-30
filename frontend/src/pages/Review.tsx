import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { AdminQuestion } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import MathText from '../components/ui/MathText';
import QuestionText from '../components/ui/QuestionText';

export default function Review() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['review'],
    queryFn: () => api.get<AdminQuestion[]>('/api/review'),
  });

  const unmark = async (id: number) => {
    await api.post(`/api/review/${id}/unmark`);
    queryClient.invalidateQueries({ queryKey: ['review'] });
  };

  if (isLoading) return <Spinner className="w-8 h-8 mt-16" />;
  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16">
        <EmptyState icon="fa-solid fa-triangle-exclamation" title="Couldn't load marked questions" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">Marked for review</h1>
      <p className="text-ink-500 mb-6">Questions you flagged to come back to.</p>

      {data && data.length > 0 ? (
        <div className="space-y-3">
          {data.map((q) => (
            <Card key={q.id} padding="md">
              <div className="font-semibold text-ink-900 mb-2 leading-relaxed"><QuestionText text={q.question_text} /></div>
              {q.image_url && (
                <img src={q.image_url} alt="Question diagram" className="w-full max-h-56 object-contain rounded-lg border border-ink-100 mb-3 bg-ink-50" />
              )}
              <div className="text-sm text-ink-500 mb-2 space-y-0.5">
                <p><span className="font-semibold text-ink-700">A.</span> <MathText text={q.option_a} /></p>
                <p><span className="font-semibold text-ink-700">B.</span> <MathText text={q.option_b} /></p>
                <p><span className="font-semibold text-ink-700">C.</span> <MathText text={q.option_c} /></p>
                <p><span className="font-semibold text-ink-700">D.</span> <MathText text={q.option_d} /></p>
              </div>
              <p className="text-sm text-success-600 font-semibold mb-2">Correct: {q.correct_option}</p>
              {q.explanation && <p className="text-sm text-ink-500 mb-3 leading-relaxed"><MathText text={q.explanation} /></p>}
              <button onClick={() => unmark(q.id)} className="text-xs font-semibold text-danger-500 hover:text-danger-600 inline-flex items-center gap-1">
                <i className="fa-solid fa-bookmark" /> Unmark
              </button>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon="fa-regular fa-bookmark"
          title="No marked questions yet"
          description="Mark tricky questions during a quiz and they'll show up here."
          action={
            <Link to="/subjects">
              <Button>Take a quiz</Button>
            </Link>
          }
        />
      )}
    </div>
  );
}
