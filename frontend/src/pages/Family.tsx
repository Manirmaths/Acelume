import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '../api/client';
import type { ChildSummary, LinkedChild, MyCode } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import useDocumentMeta from '../hooks/useDocumentMeta';

function MyCodeCard() {
  const [regenerating, setRegenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['my-guardian-code'],
    queryFn: () => api.get<MyCode>('/api/family/my-code'),
  });

  const copy = async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can be unavailable (e.g. non-HTTPS, older WebView) --
      // the code is still visible on screen either way, so this isn't fatal.
    }
  };

  const regenerate = async () => {
    if (regenerating) return;
    if (!confirm('Generate a new code? Anyone who only has your old code will no longer be able to link.')) return;
    setRegenerating(true);
    try {
      await api.post<MyCode>('/api/family/my-code/regenerate');
      await queryClient.invalidateQueries({ queryKey: ['my-guardian-code'] });
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <Card padding="lg">
      <h2 className="font-display font-bold text-sm text-ink-900 mb-1">
        <i className="fa-solid fa-share-nodes text-brand-500 mr-1.5" />
        Your sharing code
      </h2>
      <p className="text-xs text-ink-500 mb-4">
        Give this to a parent, guardian, or tutor so they can see your progress — they can never log
        in as you or change anything.
      </p>
      {isLoading || !data ? (
        <Spinner className="w-5 h-5" />
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono font-bold text-lg tracking-widest bg-ink-50 border border-ink-100 rounded-lg px-3 py-1.5">
            {data.code}
          </span>
          <Button size="sm" variant="outline" onClick={copy}>
            {copied ? 'Copied!' : 'Copy'}
          </Button>
          <Button size="sm" variant="ghost" onClick={regenerate} loading={regenerating}>
            Generate new code
          </Button>
        </div>
      )}
    </Card>
  );
}

function AddChildCard({ onLinked }: { onLinked: () => void }) {
  const [code, setCode] = useState('');
  const [linking, setLinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!code.trim() || linking) return;
    setLinking(true);
    setError(null);
    try {
      await api.post('/api/family/link', { code: code.trim() });
      setCode('');
      onLinked();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not link that code.');
    } finally {
      setLinking(false);
    }
  };

  return (
    <Card padding="lg">
      <h2 className="font-display font-bold text-sm text-ink-900 mb-1">
        <i className="fa-solid fa-user-plus text-brand-500 mr-1.5" />
        Watch someone's progress
      </h2>
      <p className="text-xs text-ink-500 mb-4">
        Enter a student's sharing code — useful for a parent watching their child, or a tutor watching
        several students.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="e.g. A1B2C3D4"
          className="max-w-[180px] font-mono uppercase"
        />
        <Button size="sm" onClick={submit} loading={linking}>
          Link
        </Button>
      </div>
      {error && <p className="text-xs text-danger-600 mt-2">{error}</p>}
    </Card>
  );
}

function ChildRow({ child, onUnlinked }: { child: LinkedChild; onUnlinked: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [unlinking, setUnlinking] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ['child-summary', child.id],
    queryFn: () => api.get<ChildSummary>(`/api/family/children/${child.id}/summary`),
    enabled: expanded,
  });

  const unlink = async () => {
    if (unlinking) return;
    if (!confirm(`Stop watching ${child.username}'s progress?`)) return;
    setUnlinking(true);
    try {
      await api.delete(`/api/family/children/${child.id}`);
      onUnlinked();
    } finally {
      setUnlinking(false);
    }
  };

  return (
    <Card padding="md">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-3 flex-1 min-w-0 text-left"
        >
          <div className="w-9 h-9 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center text-sm font-bold flex-shrink-0">
            {child.username.slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-ink-900 text-sm truncate">{child.username}</p>
            <p className="text-xs text-ink-400">
              <i className="fa-solid fa-fire text-flame-500 mr-1" />
              {child.current_streak}d streak · {child.points} pts
            </p>
          </div>
          <i className={`fa-solid fa-chevron-${expanded ? 'up' : 'down'} text-ink-300 ml-auto`} />
        </button>
        <Button size="sm" variant="ghost" onClick={unlink} loading={unlinking}>
          <i className="fa-solid fa-link-slash" />
        </Button>
      </div>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-ink-100">
          {isLoading || !data ? (
            <Spinner className="w-5 h-5" />
          ) : (
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold text-ink-500 mb-1">Projected JAMB score</p>
                {data.score_estimate.available ? (
                  <p className="font-display font-bold text-lg text-ink-900">
                    {data.score_estimate.projected_low}–{data.score_estimate.projected_high}
                    <span className="text-xs font-semibold text-ink-400"> / 400</span>
                  </p>
                ) : (
                  <p className="text-xs text-ink-500">{data.score_estimate.message}</p>
                )}
              </div>
              <div>
                <p className="text-xs font-semibold text-ink-500 mb-1">Weakest topics</p>
                {data.recommended_topics.length > 0 ? (
                  <ul className="space-y-0.5">
                    {data.recommended_topics.map((t) => (
                      <li key={t.topic} className="text-xs text-ink-700">
                        {t.topic} <span className="text-ink-400">({t.percentage}%)</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-ink-500">Not enough practice yet to tell.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function Family() {
  useDocumentMeta('Family', 'Link a parent, guardian, or tutor to watch your Acelume progress -- read-only, no password sharing.');
  const queryClient = useQueryClient();
  const { data: children, isLoading } = useQuery({
    queryKey: ['guardian-children'],
    queryFn: () => api.get<LinkedChild[]>('/api/family/children'),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['guardian-children'] });

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <div className="mb-6">
        <h1 className="font-display font-extrabold text-2xl text-ink-900">
          <i className="fa-solid fa-people-roof text-brand-600 mr-2" />
          Family &amp; tutors
        </h1>
        <p className="text-ink-500 mt-1">
          Anyone can both share their own progress and watch someone else's — a parent watching one
          child, or a tutor watching several students, works the same way.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4 mb-6">
        <MyCodeCard />
        <AddChildCard onLinked={refresh} />
      </div>

      <h2 className="font-display font-bold text-lg text-ink-900 mb-3">Who you're watching</h2>
      {isLoading ? (
        <Spinner className="w-6 h-6" />
      ) : !children || children.length === 0 ? (
        <EmptyState
          icon="fa-solid fa-people-roof"
          title="Not watching anyone yet"
          description="Enter someone's sharing code above to see their progress here."
        />
      ) : (
        <div className="space-y-3">
          {children.map((c) => (
            <ChildRow key={c.id} child={c} onUnlinked={refresh} />
          ))}
        </div>
      )}

      <p className="text-xs text-ink-400 mt-8">
        <Link to="/dashboard" className="hover:text-ink-600">
          <i className="fa-solid fa-arrow-left mr-1" /> Back to your dashboard
        </Link>
      </p>
    </div>
  );
}
