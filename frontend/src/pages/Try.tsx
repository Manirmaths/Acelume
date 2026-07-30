import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { GuestPractice } from '../api/types';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import MathText from '../components/ui/MathText';
import QuestionText from '../components/ui/QuestionText';
import useDocumentMeta from '../hooks/useDocumentMeta';

const SUBJECTS = [
  'Mathematics', 'English', 'Physics', 'Chemistry', 'Biology', 'Geography',
  'Economics', 'Literature', 'Government', 'Commerce', 'Accounting',
];

const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const;

function GuestQuestionCard({
  index,
  total,
  question,
  onAnswered,
  onNext,
}: {
  index: number;
  total: number;
  question: GuestPractice['questions'][number];
  onAnswered: (correct: boolean) => void;
  onNext: () => void;
}) {
  const [picked, setPicked] = useState<string | null>(null);
  const isLast = index === total - 1;

  const options: Record<string, string> = {
    A: question.option_a,
    B: question.option_b,
    C: question.option_c,
    D: question.option_d,
  };

  const pick = (key: string) => {
    if (picked) return;
    setPicked(key);
    onAnswered(key === question.correct_option);
  };

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs bg-ink-100 text-ink-500 rounded-full px-2.5 py-1 font-semibold">
          {question.subject} · {question.topic}
        </span>
        <span className="text-xs text-ink-400 font-semibold">
          {index + 1} / {total}
        </span>
      </div>
      <QuestionText text={question.question_text} className="text-sm font-semibold text-ink-900 leading-relaxed block mb-4" />
      <div className="space-y-2">
        {OPTION_KEYS.map((key) => {
          const isCorrect = picked !== null && key === question.correct_option;
          const isWrongPick = picked === key && key !== question.correct_option;
          return (
            <button
              key={key}
              type="button"
              onClick={() => pick(key)}
              disabled={picked !== null}
              className={`w-full text-left text-sm rounded-xl border px-3.5 py-2.5 transition-colors ${
                isCorrect
                  ? 'border-success-400 bg-success-50 text-success-700'
                  : isWrongPick
                  ? 'border-danger-400 bg-danger-50 text-danger-700'
                  : 'border-ink-200 hover:border-brand-300 hover:bg-brand-50/50 disabled:hover:border-ink-200 disabled:hover:bg-transparent'
              }`}
            >
              <span className="font-bold mr-2">{key}.</span>
              <MathText text={options[key]} />
            </button>
          );
        })}
      </div>
      {picked && (
        <>
          {question.explanation && (
            <p className="text-xs text-ink-500 mt-4 leading-relaxed">
              <i className="fa-solid fa-circle-info mr-1" />
              <MathText text={question.explanation} />
            </p>
          )}
          {/* Advancing is deliberately manual. This previously auto-advanced
              900ms after answering, which is far too short to read an
              explanation -- the whole point of the feature is learning why an
              answer is right, so the visitor decides when to move on. */}
          <div className="mt-5 flex justify-end">
            <Button onClick={onNext} icon={<i className="fa-solid fa-arrow-right" />}>
              {isLast ? 'See results' : 'Next question'}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

function SubjectPicker({ onPick }: { onPick: (subject: string) => void }) {
  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16">
      <h1 className="font-display font-extrabold text-3xl text-ink-900 mb-2">Try a free sample</h1>
      <p className="text-ink-500 mb-8">
        Pick a subject and answer 10 real questions — no account needed. Sign up any time to save your
        progress, track weak topics, and unlock every practice mode.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {SUBJECTS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="text-left text-sm font-semibold text-ink-800 bg-white border border-ink-200 rounded-xl px-4 py-3 hover:border-brand-300 hover:bg-brand-50/50 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function GuestSession({ subject, onExit }: { subject: string; onExit: () => void }) {
  const [index, setIndex] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['guest-practice', subject],
    queryFn: () => api.get<GuestPractice>(`/api/public/guest-practice?subject=${encodeURIComponent(subject)}`),
  });

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-24 flex justify-center">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  if (isError || !data || data.questions.length === 0) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16 text-center">
        <p className="text-ink-500 mb-6">Couldn't load sample questions for {subject} right now.</p>
        <Button variant="outline" onClick={onExit}>Choose another subject</Button>
      </div>
    );
  }

  const questions = data.questions;
  const finished = index >= questions.length;

  const onAnswered = (wasCorrect: boolean) => {
    if (wasCorrect) setCorrect((c) => c + 1);
    setAnsweredCount((c) => c + 1);
  };

  // Separate from onAnswered so the explanation stays on screen until the
  // visitor is done reading it -- see the note in GuestQuestionCard.
  const goNext = () => setIndex((i) => i + 1);

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16">
      <button onClick={onExit} className="text-sm font-semibold text-ink-500 hover:text-ink-800 mb-6">
        <i className="fa-solid fa-arrow-left mr-1.5" /> Choose another subject
      </button>

      {!finished ? (
        // key= is load-bearing, not cosmetic: GuestQuestionCard keeps the
        // visitor's choice in local `picked` state. Without a key React
        // reuses the same instance as `index` advances, so `picked` survives
        // into the next question -- every option renders disabled
        // (`disabled={picked !== null}`) and pick() returns early, which made
        // questions 2-10 unanswerable. Same reasoning as the key={subject} on
        // GuestSession below.
        <GuestQuestionCard
          key={questions[index].id}
          index={index}
          total={questions.length}
          question={questions[index]}
          onAnswered={onAnswered}
          onNext={goNext}
        />
      ) : (
        <Card padding="lg" className="text-center">
          <h2 className="font-display font-extrabold text-2xl text-ink-900 mb-2">
            {correct} / {answeredCount} correct
          </h2>
          <p className="text-ink-500 mb-6 max-w-sm mx-auto">
            That's just a taste — create a free account to get a full topic breakdown, an AI tutor for every
            question, spaced-repetition review, and a full JAMB CBT mock.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link to="/register">
              <Button size="lg" icon={<i className="fa-solid fa-arrow-right" />}>Create a free account</Button>
            </Link>
            <Button variant="outline" size="lg" onClick={onExit}>Try another subject</Button>
          </div>
        </Card>
      )}
    </div>
  );
}

export default function Try() {
  useDocumentMeta(
    'Try a free sample',
    'Answer 10 real JAMB, WAEC and NECO practice questions for free -- no account needed.'
  );
  const [subject, setSubject] = useState<string | null>(null);

  if (!subject) return <SubjectPicker onPick={setSubject} />;
  // key= forces a fresh session (fresh query + fresh local state) when the
  // visitor picks a different subject after finishing one.
  return <GuestSession key={subject} subject={subject} onExit={() => setSubject(null)} />;
}
