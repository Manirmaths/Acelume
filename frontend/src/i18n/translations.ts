/**
 * First-increment Hausa translation (Phase 6). Deliberately narrow scope:
 * navigation, the homepage hero, and auth-page labels -- the highest-traffic
 * public-facing strings, not full app coverage. Everything not listed here
 * falls back to English automatically (see useTranslation's `t()`).
 *
 * IMPORTANT: these Hausa strings have not been reviewed by a native speaker.
 * They're a reasonable-effort first pass, not a guarantee of accuracy --
 * education-specific terminology in particular is easy to get subtly wrong.
 * Recommend a native-speaker review pass before treating this as
 * production-complete or expanding coverage further.
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
    'home.heroTitle1': 'Your ambition.',
    'home.heroTitle2': 'Within reach.',
    'home.heroSubtitle':
      'Acelume gives you focused subject and topic practice, an AI tutor, a full JAMB CBT mock, spaced-repetition review, and progress tracking built specifically for Nigerian students.',
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
    'nav.leaderboard': 'Jerin Gasa',
    'nav.blitz': 'Blitz',
    'nav.mock': 'Cikakken Jarrabawa',
    'nav.studyPlanner': 'Tsarin Karatu',
    'nav.flashcards': 'Katunan Tunani',
    'nav.achievements': 'Nasarori',
    'nav.review': 'Alamun Bita',
    'nav.family': 'Iyali & Malamai',
    'nav.admin': 'Admin',
    'nav.login': 'Shiga',
    'nav.getStarted': 'Fara Kyauta',
    'nav.goToDashboard': 'Zuwa Dashboard',

    'home.badge': 'JAMB · WAEC · NECO · Post-UTME',
    'home.heroTitle1': 'Yi karatu da hikima.',
    'home.heroTitle2': 'Shiga jarrabawa a shirye.',
    'home.heroSubtitle':
      'Acelume na baka atisaye a kan kowane fanni da batun karatu, malamin AI, cikakkiyar jarrabawar JAMB (CBT), bita mai tazarar lokaci, da bin diddigin ci gabanka -- an tsara musamman domin daliban Najeriya.',
    'home.ctaTry': 'Gwada tambayoyi 10 kyauta',
    'home.ctaDashboard': 'Zuwa dashboard naka',
    'home.ctaMock': 'Yi jarrabawar CBT ta gwaji',
    'home.ctaRegister': 'Bude asusu kyauta',
    'home.noCard': 'Ba a bukatar bude asusu don gwada samfur -- ba a bukatar katin banki, koda yaushe.',

    'auth.emailLabel': 'Imel',
    'auth.passwordLabel': 'Kalmar sirri',
    'auth.usernameLabel': 'Sunan mai amfani',
    'auth.loginButton': 'Shiga',
    'auth.registerButton': 'Bude asusu',
    'auth.forgotPassword': 'Ka manta da kalmar sirri?',
  },
};
