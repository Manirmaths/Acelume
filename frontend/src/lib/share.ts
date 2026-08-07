/**
 * Sharing a challenge.
 *
 * The thing this replaces: the code was rendered as plain text, so a student
 * had to read six characters off the screen, hold them in their head, switch
 * to WhatsApp and type them in. That is the actual reason challenges were hard
 * to start — not the absence of a friends list.
 *
 * It matters more than it looks, because a shared link is also the app's best
 * acquisition channel. A challenge sent into a WhatsApp group can reach
 * someone who is NOT on Acelume and recruit them; a friend request can only
 * ever reach someone already there. In a market where WhatsApp groups are how
 * everything spreads, this is the growth loop.
 */

export interface ShareResult {
  /** 'shared' via the OS sheet, 'copied' to the clipboard, or 'failed'. */
  outcome: 'shared' | 'copied' | 'failed';
}

/** Where a challenge link points. Same origin, so it works in the app's WebView. */
export function challengeUrl(code: string): string {
  return `${window.location.origin}/battles/${code}`;
}

export function challengeMessage(code: string, subject?: string | null): string {
  const what = subject ? `${subject} challenge` : 'challenge';
  return (
    `I've set you a ${what} on Acelume — ${code}\n\n` +
    `Same questions for both of us, best score wins.\n` +
    `${challengeUrl(code)}`
  );
}

/**
 * Share via the OS sheet, falling back to the clipboard.
 *
 * `navigator.share` needs a user gesture and HTTPS, and is absent on desktop
 * Firefox and older Android WebViews — so the clipboard fallback is the
 * common path on a laptop and the rare path on a phone, which is the right
 * way round for this audience.
 *
 * A cancelled share is reported as 'failed' rather than surfaced as an error:
 * the student closed the sheet on purpose and does not need to be told
 * anything about it.
 */
export async function shareChallenge(code: string, subject?: string | null): Promise<ShareResult> {
  const text = challengeMessage(code, subject);

  if (typeof navigator !== 'undefined' && navigator.share) {
    try {
      await navigator.share({ title: 'Acelume challenge', text });
      return { outcome: 'shared' };
    } catch {
      // Cancelled, or the sheet is unavailable. Fall through to the clipboard
      // rather than leaving the student with nothing.
    }
  }

  try {
    await navigator.clipboard.writeText(text);
    return { outcome: 'copied' };
  } catch {
    return { outcome: 'failed' };
  }
}

/** Copy just the code, for someone typing it into the join box by hand. */
export async function copyCode(code: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(code);
    return true;
  } catch {
    return false;
  }
}
