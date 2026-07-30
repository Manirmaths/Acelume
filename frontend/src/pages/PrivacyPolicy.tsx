import useDocumentMeta from '../hooks/useDocumentMeta';

export default function PrivacyPolicy() {
  useDocumentMeta('Privacy Policy', 'How Acelume collects, uses, and protects your data.');
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16">
      <h1 className="font-display font-extrabold text-3xl text-ink-900 mb-2">Privacy Policy</h1>
      <p className="text-sm text-ink-400 mb-10">Last updated: July 2026</p>

      <div className="space-y-8 text-ink-700 leading-relaxed">
        <section>
          <p>
            Acelume ("we", "us", "our"), by Arewa Tutorials, provides exam-preparation practice for JAMB, WAEC,
            NECO and Post-UTME candidates in Nigeria, via our website (acelume.ng) and our Android app.
            This policy explains what information we collect, how we use it, and the choices you have.
          </p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Information we collect</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li><span className="font-semibold text-ink-900">Account information:</span> username, email address, and a securely hashed password (we never store your password in plain text).</li>
            <li><span className="font-semibold text-ink-900">Practice activity:</span> the quizzes you take, questions you answer, your scores, streaks, points, and topics you mark for review — used to power your dashboard and progress tracking.</li>
            <li><span className="font-semibold text-ink-900">Technical data:</span> standard server logs (IP address, browser/device type, request timestamps) generated automatically by any web request, used only for security and troubleshooting.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">How we use your information</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>To create and secure your account, and keep you logged in.</li>
            <li>To run the core product: generating quizzes, scoring answers, tracking streaks/points, and showing your personal progress dashboard.</li>
            <li>To send you a password-reset email if you request one.</li>
            <li>To maintain the leaderboard, which shows your username and points to other users (you can't opt out of the leaderboard individually today, but nothing beyond username/points/streak is shown).</li>
          </ul>
          <p className="mt-2">We do not sell your personal information, and we do not use your data for advertising.</p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Third parties we use</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li><span className="font-semibold text-ink-900">Resend</span> — sends password-reset emails on our behalf. Resend only receives your email address and the reset link at the moment you request a reset.</li>
            <li><span className="font-semibold text-ink-900">Hosting providers</span> (our servers and database) — process data only to run the app; they don't use it for their own purposes.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Your choices</h2>
          <p>
            You can review and update your account details, or ask us to delete your account and associated
            data — see our{' '}
            <a href="/delete-account" className="text-brand-600 font-semibold">account deletion page</a>{' '}
            for how. We'll action deletion requests within a reasonable time, except where we're required to
            retain limited records by law.
          </p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Children's privacy</h2>
          <p>
            Acelume is intended for students preparing for JAMB/WAEC/NECO/Post-UTME, typically aged 16 and
            older. It is not directed at children under 13, and we do not knowingly collect personal
            information from children under 13.
          </p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Cookies</h2>
          <p>
            We use a single essential, httpOnly authentication cookie to keep you logged in. We don't use
            advertising or third-party tracking cookies.
          </p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Changes to this policy</h2>
          <p>
            We may update this policy as the product evolves. Material changes will be reflected by updating
            the "Last updated" date above.
          </p>
        </section>

        <section>
          <h2 className="font-display font-bold text-xl text-ink-900 mb-2">Contact</h2>
          <p>
            Questions about this policy, or requests about your data, can be sent to{' '}
            <a href="mailto:manirkhalil@gmail.com" className="text-brand-600 font-semibold">manirkhalil@gmail.com</a>.
          </p>
        </section>
      </div>
    </div>
  );
}
