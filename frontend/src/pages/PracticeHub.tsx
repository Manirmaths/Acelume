import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Dashboard as DashboardData } from '../api/types';
import HubGrid, { type HubLink } from '../components/ui/HubGrid';

/**
 * Everything that involves answering questions, in one place.
 *
 * Ordering is deliberate and matches the product principle that learning work
 * outranks engagement features: review (spaced repetition the student owes
 * today) is first, competitive modes are last. See PRODUCT-ARCHITECTURE.md §5.
 */
export default function PracticeHub() {
  // Reuses the dashboard payload rather than adding an endpoint: it is
  // already cached under the same query key by Home, so arriving here from
  // the nav costs no extra request.
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardData>('/api/dashboard'),
  });

  const links: HubLink[] = [
    {
      to: '/subjects',
      icon: 'fa-solid fa-pen-to-square',
      title: 'Practice questions',
      description: 'Pick a subject and topic, then work through questions at your own pace.',
      primary: true,
    },
    {
      to: '/review',
      icon: 'fa-solid fa-rotate',
      title: 'Review due',
      description: 'Topics coming back around on your spaced-review schedule.',
      badge: data?.due_for_review_count ?? null,
    },
    {
      to: '/mock',
      icon: 'fa-solid fa-file-signature',
      title: 'Full mock exam',
      description: 'A complete timed UTME paper: English plus three subjects, 180 questions.',
    },
    {
      to: '/rush',
      icon: 'fa-solid fa-fire-flame-curved',
      title: 'Rush',
      description: 'Questions get harder as you go. Three wrong and the run ends.',
    },
    {
      to: '/blitz',
      icon: 'fa-solid fa-bolt',
      title: 'Blitz',
      description: 'Three minutes, one subject, as many as you can get right.',
    },
    {
      to: '/flashcards',
      icon: 'fa-solid fa-layer-group',
      title: 'Flashcards',
      description: 'Quick recall drills on the facts worth having automatic.',
    },
    {
      to: '/battles',
      icon: 'fa-solid fa-people-arrows',
      title: 'Challenge a friend',
      description: 'Head-to-head over the same questions. Play a friend, or a practice opponent right now.',
    },
  ];

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="font-display font-extrabold text-2xl text-ink-900">Practice</h1>
      <p className="text-ink-500 mt-1 mb-6">Answer questions, sit a mock, or take someone on.</p>
      <HubGrid links={links} />
    </div>
  );
}
