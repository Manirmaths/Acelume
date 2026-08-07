import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { TutorAskResponse } from '../api/types';
import Button from './ui/Button';
import MathText from './ui/MathText';

/**
 * Ask Acelume -- the AI tutor, as a contextual affordance rather than a
 * destination.
 *
 * It is deliberately NOT in the primary navigation. A student who taps
 * "Tutor" in a nav bar arrives at an empty prompt box with no context and,
 * overwhelmingly, asks nothing. A student who taps "Explain this" underneath
 * a question they just got wrong, with the explanation still on screen, asks
 * the single most useful question they will ask all week. The affordance has
 * to live where the confusion is.
 *
 * The quick prompts exist for the same reason. "What would you like to ask?"
 * is a blank page, and a 16-year-old on a phone will not fill it in. Naming
 * the three or four things people actually want turns a writing task into a
 * tap. Free text stays available underneath for everyone else.
 *
 * Note the backend guard in routers/tutor.py: a question must already have
 * been ANSWERED before it can be discussed, so this cannot be used to fish
 * the correct option out of the AI. Only render it post-answer.
 */

interface QuickPrompt {
  label: string;
  icon: string;
  message: string;
}

const WRONG_ANSWER_PROMPTS: QuickPrompt[] = [
  { label: 'Where did I go wrong?', icon: 'fa-solid fa-circle-question', message: 'I got this wrong. Where did my reasoning go wrong?' },
  { label: 'Explain simply', icon: 'fa-solid fa-lightbulb', message: 'Explain this to me as simply as you can, like I am new to the topic.' },
  { label: 'Show the steps', icon: 'fa-solid fa-list-ol', message: 'Show me the full working, step by step.' },
  { label: 'Similar question', icon: 'fa-solid fa-clone', message: 'Give me a similar practice question to try, without the answer.' },
];

const CORRECT_ANSWER_PROMPTS: QuickPrompt[] = [
  { label: 'Why does this work?', icon: 'fa-solid fa-lightbulb', message: 'I got this right, but explain why the method actually works.' },
  { label: 'Show the steps', icon: 'fa-solid fa-list-ol', message: 'Show me the full working, step by step.' },
  { label: 'Faster method?', icon: 'fa-solid fa-gauge-high', message: 'Is there a faster way to do this in an exam?' },
  { label: 'Harder version', icon: 'fa-solid fa-arrow-trend-up', message: 'Give me a harder version of this question to try, without the answer.' },
];

export default function AskAcelume({
  questionId,
  wasCorrect = false,
  className = '',
}: {
  questionId: number;
  /** Drives which quick prompts are offered -- a student who got it right has a different question. */
  wasCorrect?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);

  const prompts = wasCorrect ? CORRECT_ANSWER_PROMPTS : WRONG_ANSWER_PROMPTS;

  const ask = async (text: string) => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setError(null);
    try {
      const res = await api.post<TutorAskResponse>('/api/tutor/ask', {
        question_id: questionId,
        message: body,
      });
      setReply(res.reply);
      setRemaining(res.queries_remaining_today);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not reach the tutor. Check your connection.');
    } finally {
      setSending(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className={`inline-flex items-center gap-1.5 text-xs font-semibold text-brand-600 hover:text-brand-700 ${className}`}
      >
        <i className="fa-solid fa-wand-magic-sparkles" aria-hidden="true" />
        {wasCorrect ? 'Ask Acelume about this' : 'Still confused? Ask Acelume'}
      </button>
    );
  }

  return (
    <div className={`mt-3 pt-3 border-t border-ink-100 ${className}`}>
      <p className="text-xs font-semibold text-ink-500 mb-2">
        <i className="fa-solid fa-wand-magic-sparkles text-brand-500 mr-1" aria-hidden="true" />
        Ask Acelume
      </p>

      {reply ? (
        <>
          <div className="text-sm text-ink-700 leading-relaxed bg-ink-50 rounded-lg p-3 whitespace-pre-wrap">
            <MathText text={reply} />
          </div>
          <div className="flex items-center justify-between gap-3 mt-2">
            <button
              onClick={() => {
                setReply(null);
                setMessage('');
              }}
              className="text-xs font-semibold text-brand-600 hover:text-brand-700"
            >
              Ask something else
            </button>
            {remaining !== null && (
              <span className="text-xs text-ink-400">{remaining} left today</span>
            )}
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {prompts.map((p) => (
              <button
                key={p.label}
                onClick={() => ask(p.message)}
                disabled={sending}
                className="inline-flex items-center gap-1.5 text-xs font-medium rounded-full border border-ink-200 bg-white px-2.5 py-1.5 text-ink-700 hover:border-brand-300 hover:bg-brand-50 disabled:opacity-50"
              >
                <i className={`${p.icon} text-brand-500`} aria-hidden="true" />
                {p.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && ask(message)}
              placeholder="Or ask in your own words…"
              aria-label="Ask the tutor about this question"
              className="flex-1 min-w-[180px] text-sm rounded-lg border border-ink-200 px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
            <Button size="sm" onClick={() => ask(message)} disabled={sending || !message.trim()}>
              {sending ? 'Asking…' : 'Ask'}
            </Button>
          </div>
        </>
      )}

      {sending && !reply && <p className="text-xs text-ink-400 mt-2">Thinking…</p>}
      {error && <p className="text-xs text-danger-500 mt-1.5" role="alert">{error}</p>}
    </div>
  );
}
