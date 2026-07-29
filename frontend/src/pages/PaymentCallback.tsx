import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { PremiumStatus } from '../api/types';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import useDocumentMeta from '../hooks/useDocumentMeta';

// Paystack redirects the browser back here immediately after checkout, but
// the webhook that actually grants premium (POST /api/payments/webhook) is
// a separate, async, server-to-server call from Paystack -- it can arrive a
// few seconds after this redirect. So this page polls /api/payments/status
// briefly rather than trusting the redirect alone to mean "paid".
const POLL_INTERVAL_MS = 2000;
const MAX_POLLS = 10;

export default function PaymentCallback() {
  useDocumentMeta('Payment', 'Confirming your Acelume Premium payment.');
  const [status, setStatus] = useState<'checking' | 'success' | 'pending'>('checking');

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const poll = async () => {
      try {
        const data = await api.get<PremiumStatus>('/api/payments/status');
        if (cancelled) return;
        if (data.is_premium) {
          setStatus('success');
          return;
        }
      } catch {
        // ignore -- just retry on the next tick
      }
      attempts += 1;
      if (attempts >= MAX_POLLS) {
        if (!cancelled) setStatus('pending');
        return;
      }
      setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="max-w-md mx-auto px-4 sm:px-6 py-24 text-center">
      <Card padding="lg">
        {status === 'checking' && (
          <>
            <Spinner className="w-8 h-8 mx-auto mb-4" />
            <h1 className="font-display font-bold text-lg text-ink-900 mb-1">Confirming your payment…</h1>
            <p className="text-sm text-ink-500">This usually takes a few seconds.</p>
          </>
        )}
        {status === 'success' && (
          <>
            <div className="w-12 h-12 rounded-full bg-success-50 text-success-600 flex items-center justify-center text-xl mx-auto mb-4">
              <i className="fa-solid fa-check" />
            </div>
            <h1 className="font-display font-bold text-lg text-ink-900 mb-2">You're Premium!</h1>
            <p className="text-sm text-ink-500 mb-6">Unlimited full mock exams and everything else, unlocked.</p>
            <Link to="/mock">
              <Button size="lg">Take a mock exam</Button>
            </Link>
          </>
        )}
        {status === 'pending' && (
          <>
            <div className="w-12 h-12 rounded-full bg-warning-50 text-warning-600 flex items-center justify-center text-xl mx-auto mb-4">
              <i className="fa-solid fa-clock" />
            </div>
            <h1 className="font-display font-bold text-lg text-ink-900 mb-2">Still processing</h1>
            <p className="text-sm text-ink-500 mb-6">
              Your payment is being confirmed — this can occasionally take a minute. Check your dashboard shortly.
            </p>
            <Link to="/dashboard">
              <Button variant="outline" size="lg">Go to dashboard</Button>
            </Link>
          </>
        )}
      </Card>
    </div>
  );
}
