import { useState } from 'react';
import Button from './ui/Button';
import { copyCode, shareChallenge } from '../lib/share';

/**
 * The share control for a challenge code.
 *
 * Two actions on purpose. "Send challenge" opens the OS share sheet with the
 * message already written, which is what a student on a phone actually wants —
 * it lands them in WhatsApp with everything filled in. "Copy code" is for the
 * person who is going to read it out or type it into the join box.
 *
 * The code stays visible next to both. A student reading it aloud to the
 * person beside them is a real and common case, and hiding it behind a button
 * would break it.
 */
export default function ShareChallenge({
  code,
  subject,
  className = '',
}: {
  code: string;
  subject?: string | null;
  className?: string;
}) {
  const [status, setStatus] = useState<string | null>(null);

  const flash = (message: string) => {
    setStatus(message);
    window.setTimeout(() => setStatus(null), 2200);
  };

  const send = async () => {
    const { outcome } = await shareChallenge(code, subject);
    if (outcome === 'shared') return;                 // the sheet is its own feedback
    if (outcome === 'copied') flash('Challenge copied — paste it to your friend');
    else flash('Could not share. Read them the code instead.');
  };

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={send} icon={<i className="fa-solid fa-share-nodes" />}>
          Send challenge
        </Button>
        <button
          onClick={async () => flash(await copyCode(code) ? 'Code copied' : 'Could not copy')}
          className="inline-flex items-center gap-2 rounded-xl border border-ink-200 px-3 py-2.5 text-sm font-mono font-bold tracking-widest text-ink-800 hover:border-brand-300 hover:bg-brand-50"
          title="Copy just the code"
        >
          {code}
          <i className="fa-regular fa-copy text-ink-400 text-xs" aria-hidden="true" />
        </button>
      </div>
      {status && (
        <p className="text-xs text-success-600 mt-2" role="status">
          {status}
        </p>
      )}
    </div>
  );
}
