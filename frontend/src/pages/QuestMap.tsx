import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { QuestMap as QuestMapData, QuestTopic, QuizAttempt } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import useDocumentMeta from '../hooks/useDocumentMeta';

/**
 * Every state carries an ICON and a LABEL as well as a colour, because colour
 * alone fails for colour-blind students and in high-contrast modes. The spec
 * requires this explicitly.
 */
const STATE_META: Record<
  string,
  { label: string; icon: string; dot: string; card: string }
> = {
  locked: {
    label: 'Locked',
    icon: 'fa-solid fa-lock',
    dot: 'bg-ink-200 text-ink-500',
    card: 'border-ink-100 bg-ink-50/60',
  },
  available: {
    label: 'Ready to start',
    icon: 'fa-regular fa-circle',
    dot: 'bg-white text-ink-500 border border-ink-300',
    card: 'border-ink-200 bg-white hover:border-brand-300',
  },
  learning: {
    label: 'Lesson read',
    icon: 'fa-solid fa-book-open',
    dot: 'bg-brand-100 text-brand-600',
    card: 'border-brand-200 bg-brand-50/40 hover:border-brand-300',
  },
  practising: {
    label: 'Practising',
    icon: 'fa-solid fa-pen-to-square',
    dot: 'bg-brand-100 text-brand-600',
    card: 'border-brand-200 bg-brand-50/40 hover:border-brand-300',
  },
  proficient: {
    label: 'Proficient',
    icon: 'fa-solid fa-circle-check',
    dot: 'bg-brand-500 text-white',
    card: 'border-brand-300 bg-brand-50/60 hover:border-brand-400',
  },
  mastered: {
    label: 'Mastered',
    icon: 'fa-solid fa-trophy',
    dot: 'bg-success-500 text-white',
    card: 'border-success-300 bg-success-50/60 hover:border-success-400',
  },
  review_due: {
    label: 'Review due',
    icon: 'fa-solid fa-clock-rotate-left',
    dot: 'bg-warning-500 text-white',
    card: 'border-warning-300 bg-warning-50/60 hover:border-warning-400',
  },
};

function Stars({ count }: { count: number }) {
  return (
    <span className="flex items-center gap-0.5" aria-label={`${count} of 3 stars`}>
      {[1, 2, 3].map((n) => (
        <i
          key={n}
          aria-hidden="true"
          className={`fa-solid fa-star text-[11px] ${n <= count ? 'text-warning-500' : 'text-ink-200'}`}
        />
      ))}
    </span>
  );
}

function TopicRow({
  topic,
  subject,
  isLast,
  onTestOut,
  testingOut,
}: {
  topic: QuestTopic;
  subject: string;
  isLast: boolean;
  onTestOut: (topic: string) => void;
  testingOut: string | null;
}) {
  const meta = STATE_META[topic.state] ?? STATE_META.available;
  const locked = topic.state === 'locked';

  const body = (
    <Card padding="md" className={`transition-colors ${meta.card}`}>
      <div className="flex items-start gap-3">
        <div
          className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${meta.dot}`}
          aria-hidden="true"
        >
          <i className={`${meta.icon} text-xs`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className={`font-semibold text-sm ${locked ? 'text-ink-500' : 'text-ink-900'}`}>
              {topic.topic}
            </p>
            <Stars count={topic.stars} />
          </div>
          <p className="text-xs text-ink-500 mt-0.5">
            {meta.label}
            {topic.estimated_minutes ? ` · about ${topic.estimated_minutes} min` : ''}
            {topic.mastery_score > 0 ? ` · ${topic.mastery_score}% mastery` : ''}
          </p>
          {locked && topic.prerequisite && (
            <p className="text-xs text-ink-400 mt-1">
              Unlocks after <span className="font-medium">{topic.prerequisite}</span>
            </p>
          )}
        </div>

        {locked ? (
          <Button
            size="sm"
            variant="outline"
            disabled={testingOut === topic.topic}
            onClick={(e) => {
              e.preventDefault();
              onTestOut(topic.topic);
            }}
          >
            {testingOut === topic.topic ? 'Starting…' : 'Test out'}
          </Button>
        ) : (
          <i className="fa-solid fa-chevron-right text-ink-300 text-xs mt-3" aria-hidden="true" />
        )}
      </div>
    </Card>
  );

  return (
    <li className="relative">
      {/* Connecting path between nodes. Purely decorative. */}
      {!isLast && (
        <span
          aria-hidden="true"
          className="absolute left-[30px] top-full h-3 w-px bg-ink-200"
        />
      )}
      {locked ? (
        body
      ) : (
        <Link
          to={`/subjects/${encodeURIComponent(subject)}/topics/${encodeURIComponent(topic.topic)}`}
          className="block"
        >
          {body}
        </Link>
      )}
    </li>
  );
}

export default function QuestMap() {
  const { subject = '' } = useParams();
  const navigate = useNavigate();
  const [testingOut, setTestingOut] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useDocumentMeta(`${subject} quest map`, `Track your progress through every ${subject} topic.`);

  const { data, isLoading, error: loadError } = useQuery({
    queryKey: ['quest', subject],
    queryFn: () => api.get<QuestMapData>(`/api/quest/${encodeURIComponent(subject)}`),
    retry: false,
  });

  const startTestOut = async (topic: string) => {
    setTestingOut(topic);
    setError(null);
    try {
      const attempt = await api.post<QuizAttempt>(
        `/api/quest/${encodeURIComponent(subject)}/${encodeURIComponent(topic)}/test-out`
      );
      navigate(`/quiz-attempt/${attempt.attempt_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start the test-out challenge.');
      setTestingOut(null);
    }
  };

  if (isLoading) return <Spinner className="w-8 h-8 mt-16" />;

  if (loadError || !data) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16">
        <EmptyState
          icon="fa-solid fa-map"
          title="No quest map yet"
          description={`The syllabus for ${subject} hasn't been set up yet. Regular practice still works.`}
          action={<Link to="/subjects"><Button>Browse subjects</Button></Link>}
        />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900 mb-1">{data.subject}</h1>
      <p className="text-ink-500 mb-5">
        {data.mastered_topics} of {data.total_topics} topics mastered
        {data.review_due_topics > 0 && ` · ${data.review_due_topics} due for review`}
      </p>

      <div className="mb-6">
        <div className="h-2 rounded-full bg-ink-100 overflow-hidden">
          <div
            className="h-full bg-success-500 transition-all"
            style={{ width: `${data.percent_complete}%` }}
            role="progressbar"
            aria-valuenow={data.percent_complete}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${data.percent_complete}% of ${data.subject} mastered`}
          />
        </div>
      </div>

      {data.recommended_topic && (
        <Card padding="md" className="mb-6 bg-brand-50 border-brand-100 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-brand-800 font-medium">
            <i className="fa-solid fa-wand-magic-sparkles mr-1.5" aria-hidden="true" />
            Continue with <span className="font-bold">{data.recommended_topic}</span>
          </p>
          <Link
            to={`/subjects/${encodeURIComponent(subject)}/topics/${encodeURIComponent(data.recommended_topic)}`}
          >
            <Button size="sm">Continue learning</Button>
          </Link>
        </Card>
      )}

      {error && (
        <p className="text-sm text-danger-600 mb-4" role="alert">{error}</p>
      )}

      <ol className="space-y-3">
        {data.topics.map((t, i) => (
          <TopicRow
            key={t.topic}
            topic={t}
            subject={subject}
            isLast={i === data.topics.length - 1}
            onTestOut={startTestOut}
            testingOut={testingOut}
          />
        ))}
      </ol>

      <p className="text-xs text-ink-400 mt-6 leading-relaxed">
        Earn stars by reading the lesson, then practising {data.practice_pass_pct}% or better,
        then passing a timed challenge at {data.challenge_pass_pct}%. Mastered topics come back
        for review so they stay learned.
      </p>
    </div>
  );
}
