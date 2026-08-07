import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Insight } from '../api/types';
import Card from './ui/Card';

/**
 * What's actually costing you marks.
 *
 * Statements, not charts. The reason chess.com's Insights works is that it
 * says "you lose most of your games in the endgame" rather than drawing you a
 * graph and leaving you to work it out. Acelume already renders plenty of
 * percentages; the value added here is entirely in the phrasing.
 *
 * Renders nothing when there is nothing true to say. A panel that always has
 * content teaches students that its content is filler, and then they stop
 * reading the one week it matters.
 */
export default function Insights() {
  const { data } = useQuery({
    queryKey: ['insights'],
    queryFn: () => api.get<Insight[]>('/api/dashboard/insights'),
    retry: false,
  });

  if (!data || data.length === 0) return null;

  return (
    <Card padding="lg" className="mb-6">
      <h2 className="font-display font-bold text-ink-900 mb-4">
        What's actually costing you marks
      </h2>

      <div className="space-y-4">
        {data.map((insight) => (
          <div key={insight.key} className="flex items-start gap-3">
            <i className={`${insight.icon} text-brand-500 mt-0.5 w-4 text-center`} aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-ink-800 leading-snug">{insight.text}</p>
              {insight.action_label && insight.action_href && (
                <Link
                  to={insight.action_href}
                  className="inline-block mt-1.5 text-xs font-semibold text-brand-600 hover:text-brand-700"
                >
                  {insight.action_label} →
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
