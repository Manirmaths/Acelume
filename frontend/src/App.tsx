import { Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import PublicLayout from './components/PublicLayout';
import AppShell from './components/AppShell';
import RequireAuth from './components/RequireAuth';
import Spinner from './components/ui/Spinner';

// Route-level code splitting: each page becomes its own JS chunk instead of
// all being bundled into one file loaded up front. This matters most on a
// slow/mobile connection (which is most of this app's traffic) and for the
// Android app's first launch -- the initial bundle only has to contain the
// router/auth shell, and e.g. the rarely-used Admin page's code never loads
// for a regular student at all.
const Home = lazy(() => import('./pages/Home'));
const Try = lazy(() => import('./pages/Try'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy'));
const DeleteAccount = lazy(() => import('./pages/DeleteAccount'));
const Subjects = lazy(() => import('./pages/Subjects'));
const SubjectTopics = lazy(() => import('./pages/SubjectTopics'));
const QuestMap = lazy(() => import('./pages/QuestMap'));
const TopicHub = lazy(() => import('./pages/TopicHub'));
const LearnHub = lazy(() => import('./pages/LearnHub'));
const Quiz = lazy(() => import('./pages/Quiz'));
const Results = lazy(() => import('./pages/Results'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Leaderboard = lazy(() => import('./pages/Leaderboard'));
const Blitz = lazy(() => import('./pages/Blitz'));
const Mock = lazy(() => import('./pages/Mock'));
const MockExam = lazy(() => import('./pages/MockExam'));
const PaymentCallback = lazy(() => import('./pages/PaymentCallback'));
const Family = lazy(() => import('./pages/Family'));
const Achievements = lazy(() => import('./pages/Achievements'));
const StudyPlanner = lazy(() => import('./pages/StudyPlanner'));
const Flashcards = lazy(() => import('./pages/Flashcards'));
const Review = lazy(() => import('./pages/Review'));
const Admin = lazy(() => import('./pages/Admin'));
const NotFound = lazy(() => import('./pages/NotFound'));

function PageLoader() {
  return (
    <div className="flex justify-center py-24">
      <Spinner className="w-8 h-8" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/try" element={<Try />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/delete-account" element={<DeleteAccount />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route path="/subjects" element={<Subjects />} />
          <Route path="/subjects/:subject" element={<SubjectTopics />} />
          {/* Quest Map sits above the flat topic list for a subject. Placed
              before the :topic route so "quest" can't be read as a topic name. */}
          <Route path="/subjects/:subject/quest" element={<QuestMap />} />
          <Route path="/subjects/:subject/topics/:topic" element={<TopicHub />} />
          <Route path="/learn" element={<LearnHub />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/quiz-attempt/:attemptId" element={<Quiz />} />
          <Route path="/results/:attemptId" element={<Results />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/blitz" element={<Blitz />} />
          <Route path="/mock" element={<Mock />} />
          <Route path="/mock-attempt/:attemptId" element={<MockExam />} />
          <Route path="/payment-callback" element={<PaymentCallback />} />
          <Route path="/family" element={<Family />} />
          <Route path="/achievements" element={<Achievements />} />
          <Route path="/study-planner" element={<StudyPlanner />} />
          <Route path="/flashcards" element={<Flashcards />} />
          <Route path="/review" element={<Review />} />
          <Route
            path="/admin"
            element={
              <RequireAuth adminOnly>
                <Admin />
              </RequireAuth>
            }
          />
        </Route>
      </Routes>
    </Suspense>
  );
}
