/**
 * Hausa translation (Phase 6). Deliberately narrow scope: navigation, the
 * homepage hero, and auth-page labels -- the highest-traffic public-facing
 * strings, not full app coverage. Everything not listed here falls back to
 * English automatically (see useTranslation's `t()`).
 *
 * NATIVE-SPEAKER REVIEWED (2026-07-30). The Hausa strings below were revised
 * by a native speaker and supersede the original machine-drafted pass. See
 * HAUSA-REVIEW.md for what changed and why. Conventions established in that
 * review, worth preserving when adding strings:
 *
 *   - Address users with the plural/polite `ku` form (`burin ku`, `muku`,
 *     `ci gabanku`, `ɗinku`), never the gendered singular `ka`/`ki`. The
 *     English source is genderless; masculine-singular Hausa excludes roughly
 *     half the JAMB/WAEC candidate population.
 *   - Where person can be avoided entirely, prefer the impersonal
 *     construction (`An manta da password?`, `An sa wa alamar bita`).
 *   - Use proper Boko orthography with hooked letters: ɓ ɗ ƙ ƴ. These are
 *     distinct letters, not accents -- `bude`/`buɗe` and `dalibai`/`ɗaliban`
 *     are not interchangeable.
 *   - "Subject" is `darussa` consistently (not `fanni`).
 *   - `jarrabawa` is feminine, so it takes `cikakkiyar`, not `cikakken`.
 *   - Established English loanwords students already use (`Dashboard`,
 *     `Password`, `Flashcards`, `Blitz`, `Imel`, `Mock`) are kept in English
 *     deliberately -- translating them would be less clear, not more.
 */
export type Language = 'en' | 'ha';

export const LANGUAGES: { value: Language; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'ha', label: 'Hausa' },
];

type Dict = Record<string, string>;

export const translations: Record<Language, Dict> = {
  en: {
    'nav.dashboard': 'Dashboard',
    'nav.subjects': 'Subjects',
    'nav.learn': 'Learn',
    'nav.leaderboard': 'Leaderboard',
    'nav.league': 'Weekly league',
    'nav.battles': 'Challenges',
    'nav.blitz': 'Blitz',
    'nav.mock': 'Full Mock',
    'nav.studyPlanner': 'Study Planner',
    'nav.flashcards': 'Flashcards',
    'nav.achievements': 'Achievements',
    'nav.review': 'Marked for review',
    'nav.family': 'Family & tutors',
    'nav.admin': 'Admin',
    'nav.login': 'Log in',
    'nav.getStarted': 'Get Started Free',
    'nav.goToDashboard': 'Go to Dashboard',

    'home.badge': 'JAMB · WAEC · NECO · Post-UTME',
    'home.heroTitle1': 'Know your score',
    'home.heroTitle2': 'before JAMB does.',
    'home.heroSubtitle':
      'Over 10,000 real past questions, each with an explanation that actually teaches. Sit full CBT mocks under exam conditions, ask the AI tutor when an explanation is not enough, and watch your projected score sharpen every time you practise.',
    'home.ctaTry': 'Try 10 free questions',
    'home.ctaDashboard': 'Go to your dashboard',
    'home.ctaMock': 'Take a mock CBT',
    'home.ctaRegister': 'Create a free account',
    'home.noCard': "No sign-up needed to try a sample — no card required, ever.",

    'auth.emailLabel': 'Email',
    'auth.passwordLabel': 'Password',
    'auth.usernameLabel': 'Username',
    'auth.loginButton': 'Log in',
    'auth.registerButton': 'Create account',
    'auth.forgotPassword': 'Forgot password?',
  },
  ha: {
    'nav.dashboard': 'Dashboard',
    'nav.subjects': 'Darussa',
    'nav.learn': 'Koyo',
    'nav.leaderboard': 'Jerin Matsayi',
    // Untranslated: added after the native-speaker review, so these fall back
    // to English via t(). Needs a Hausa pass -- see HAUSA-REVIEW.md.
    'nav.blitz': 'Blitz',
    'nav.mock': 'Cikakkiyar jarrabawar gwaji (Mock)',
    'nav.studyPlanner': 'Tsarin karatu',
    'nav.flashcards': 'Flashcards',
    'nav.achievements': 'Nasarori',
    'nav.review': 'An sa wa alamar bita',
    'nav.family': 'Iyali da malamai',
    'nav.admin': 'Admin',
    'nav.login': 'Shiga',
    'nav.getStarted': 'Fara kyauta',
    'nav.goToDashboard': 'Je zuwa Dashboard',

    'home.badge': 'JAMB · WAEC · NECO · Post-UTME',
    // OUT OF DATE (2026-07-30): the English hero was rewritten to
    // "Know your score / before JAMB does." and a new subtitle. These three
    // Hausa strings still render the previous message ("Your ambition / It is
    // nearly fulfilled" + the old feature list), so a Hausa speaker currently
    // sees different copy from an English one. Needs a native-speaker pass --
    // see HAUSA-REVIEW.md for the conventions to follow (ku form, hooked
    // letters, darussa).
    'home.heroTitle1': 'Burin ku.',
    'home.heroTitle2': 'Ya kusa cika.',
    'home.heroSubtitle':
      'Acelume yana samar muku da atisaye na musamman kan darussa da batutuwan karatu, malamin AI, cikakkiyar jarrabawar gwaji (Mock) ta JAMB CBT, bitar da ake maimaitawa a kan tazara, da kuma hanyar bibiyar ci gabanku—duk an tsara su musamman domin ɗaliban Najeriya.',
    'home.ctaTry': 'Gwada tambayoyi 10 kyauta',
    'home.ctaDashboard': 'Je zuwa Dashboard ɗinku',
    'home.ctaMock': 'Yi jarrabawar gwaji ta CBT',
    'home.ctaRegister': 'Yi rigista kyauta',
    'home.noCard': 'Ba sai an yi rigista ba domin gwadawa—kuma ba a buƙatar katin banki ko kaɗan.',

    'auth.emailLabel': 'Imel',
    'auth.passwordLabel': 'Password',
    'auth.usernameLabel': 'Sunan mai amfani',
    'auth.loginButton': 'Shiga',
    'auth.registerButton': 'Yi rigista',
    'auth.forgotPassword': 'An manta da password?',
  },
};
