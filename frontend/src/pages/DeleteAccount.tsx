import useDocumentMeta from '../hooks/useDocumentMeta';

export default function DeleteAccount() {
  useDocumentMeta('Delete Your Account', 'How to request deletion of your Acelume account and data.');
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16">
      <h1 className="font-display font-extrabold text-3xl text-ink-900 mb-2">Delete Your Account</h1>
      <p className="text-sm text-ink-400 mb-10">Last updated: July 2026</p>

      <div className="space-y-8 text-ink-700 leading-relaxed">
        <section>
          <p>
            You can request permanent deletion of your Acelume account and all associated data at any
            time, whether you signed up on the website or the Android app.
          </p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">How to request deletion</h2>
          <p>
            Send an email to{' '}
            <a href="mailto:manirkhalil@gmail.com?subject=Account%20deletion%20request" className="text-brand-600 font-semibold">
              manirkhalil@gmail.com
            </a>{' '}
            from the email address linked to your account, with the subject line "Account deletion request".
            We'll confirm your identity and process the deletion within 7 days.
          </p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">What gets deleted</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>Your account details: username, email address, and password hash.</li>
            <li>Your practice activity: quiz attempts, answers, scores, streaks, and points.</li>
            <li>Any guardian links you've created or been linked to.</li>
            <li>Payment records are retained for a limited period as required for financial record-keeping,
              even after account deletion, but are no longer linked to an active account.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Questions</h2>
          <p>
            See our full{' '}
            <a href="/privacy" className="text-brand-600 font-semibold">Privacy Policy</a> for more on how we
            handle your data, or email{' '}
            <a href="mailto:manirkhalil@gmail.com" className="text-brand-600 font-semibold">manirkhalil@gmail.com</a>{' '}
            with any questions.
          </p>
        </section>
      </div>
    </div>
  );
}
