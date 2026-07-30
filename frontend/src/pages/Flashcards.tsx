import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Flashcard, FlashcardsResponse, Subject, Topic } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { Select } from '../components/ui/Input';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import MathText from '../components/ui/MathText';
import QuestionText from '../components/ui/QuestionText';

const COUNT_OPTIONS = [10, 20, 30];

export default function Flashcards() {
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [count, setCount] = useState(20);
  const [cards, setCards] = useState<Flashcard[] | null>(null);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: subjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => api.get<Subject[]>('/api/subjects'),
  });

  const { data: topics } = useQuery({
    queryKey: ['topics', subject],
    queryFn: () => api.get<Topic[]>(`/api/subjects/${encodeURIComponent(subject)}/topics`),
    enabled: !!subject,
  });

  const startSet = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (topic) params.set('topic', topic);
      else if (subject) params.set('subject', subject);
      params.set('n', String(count));
      const res = await api.get<FlashcardsResponse>(`/api/flashcards?${params.toString()}`);
      setCards(res.items);
      setIndex(0);
      setFlipped(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not build a flashcard set.');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setCards(null);
    setIndex(0);
    setFlipped(false);
  };

  const next = () => {
    if (!cards) return;
    setFlipped(false);
    setIndex((i) => Math.min(i + 1, cards.length - 1));
  };

  const prev = () => {
    setFlipped(false);
    setIndex((i) => Math.max(i - 1, 0));
  };

  if (cards) {
    const card = cards[index];
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <button onClick={reset} className="text-sm font-semibold text-ink-500 hover:text-ink-700">
            <i className="fa-solid fa-arrow-left mr-1.5" /> New set
          </button>
          <span className="text-sm font-semibold text-ink-400">
            {index + 1} / {cards.length}
          </span>
        </div>

        <button
          type="button"
          onClick={() => setFlipped((f) => !f)}
          className="w-full text-left"
          style={{ perspective: '1200px' }}
        >
          <div
            className="relative w-full min-h-[280px] transition-transform duration-500"
            style={{ transformStyle: 'preserve-3d', transform: flipped ? 'rotateY(180deg)' : 'none' }}
          >
            {/* Front */}
            <Card
              padding="lg"
              className="absolute inset-0 flex flex-col justify-center"
              style={{ backfaceVisibility: 'hidden' }}
            >
              {card.subject && (
                <span className="self-start text-xs bg-ink-100 text-ink-500 rounded-full px-2.5 py-1 font-semibold mb-4">
                  {card.subject} · {card.topic}
                </span>
              )}
              <QuestionText text={card.question_text} className="font-display font-bold text-lg text-ink-900 leading-relaxed" />
              {card.image_url && <img src={card.image_url} alt="" className="mt-4 max-h-40 object-contain" />}
              <p className="text-xs text-ink-400 mt-6">
                <i className="fa-solid fa-rotate mr-1" /> Tap to flip
              </p>
            </Card>

            {/* Back */}
            <Card
              padding="lg"
              className="absolute inset-0 flex flex-col justify-center bg-brand-50 border-brand-100"
              style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
            >
              <p className="text-xs font-bold text-brand-600 uppercase tracking-wide mb-2">Answer</p>
              <MathText text={card.answer_text} className="font-display font-extrabold text-xl text-ink-900" />
              {card.explanation && (
                <p className="text-sm text-ink-600 mt-4 leading-relaxed"><MathText text={card.explanation} /></p>
              )}
              <p className="text-xs text-ink-400 mt-6">
                <i className="fa-solid fa-rotate mr-1" /> Tap to flip back
              </p>
            </Card>
          </div>
        </button>

        <div className="flex items-center justify-between gap-3 mt-6">
          <Button variant="outline" onClick={prev} disabled={index === 0}>
            <i className="fa-solid fa-chevron-left mr-1.5" /> Previous
          </Button>
          {index < cards.length - 1 ? (
            <Button onClick={next}>
              Next <i className="fa-solid fa-chevron-right ml-1.5" />
            </Button>
          ) : (
            <Button onClick={reset}>
              Done <i className="fa-solid fa-check ml-1.5" />
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <div className="mb-6">
        <h1 className="font-display font-extrabold text-2xl text-ink-900">
          <i className="fa-solid fa-layer-group text-brand-500 mr-2" />
          Flashcards
        </h1>
        <p className="text-ink-500 mt-1">Quick-flip through questions and answers — no scoring, just recall practice.</p>
      </div>

      {error && (
        <Card padding="sm" className="mb-4 bg-danger-50 border-danger-100 text-danger-600 text-sm font-semibold">
          {error}
        </Card>
      )}

      <Card padding="lg">
        {!subjects ? (
          <Spinner className="w-6 h-6" />
        ) : (
          <div className="space-y-4">
            <Select
              label="Subject (optional)"
              value={subject}
              onChange={(e) => {
                setSubject(e.target.value);
                setTopic('');
              }}
            >
              <option value="">All subjects</option>
              {subjects.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </Select>

            <Select
              label="Topic (optional)"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={!subject || !topics}
            >
              <option value="">All topics</option>
              {topics?.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name}
                </option>
              ))}
            </Select>

            <div>
              <p className="text-sm font-semibold text-ink-800 mb-2">How many cards?</p>
              <div className="flex gap-2">
                {COUNT_OPTIONS.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setCount(n)}
                    className={`text-sm font-semibold rounded-full px-4 py-1.5 transition-colors ${
                      count === n ? 'bg-brand-500 text-white' : 'bg-ink-100 text-ink-600 hover:bg-ink-200'
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <Button size="lg" fullWidth onClick={startSet} disabled={loading}>
              {loading ? 'Building…' : 'Start flashcards'}
            </Button>
          </div>
        )}
      </Card>

      {subjects && subjects.length === 0 && (
        <EmptyState icon="fa-solid fa-layer-group" title="No subjects available" />
      )}
    </div>
  );
}
