export interface User {
  id: number;
  username: string;
  email: string;
  points: number;
  is_admin: boolean;
  is_premium: boolean;
  current_streak: number;
  longest_streak: number;
  streak_freezes: number;
  daily_goal: number;
  has_taken_diagnostic: boolean;
}

export interface Subject {
  name: string;
  question_count: number;
}

export interface Topic {
  name: string;
  count: number;
}

export type Difficulty = 'easy' | 'medium' | 'hard';
export type QuestionSource = 'original' | 'past-question' | 'licensed';
export type QuestionStatus = 'active' | 'draft';

export interface Passage {
  passage_id: string;
  subject: string | null;
  title: string | null;
  passage_text: string;
}

export interface QuestionPublic {
  id: number;
  question_id: string | null;
  subject: string | null;
  topic: string | null;
  subtopic: string | null;
  difficulty: Difficulty;
  question_text: string;
  image_url: string | null;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  year: string | null;
  passage: Passage | null;
}

export interface QuizAttempt {
  attempt_id: number;
  mode: string;
  total: number;
  current_index: number;
  time_limit_seconds: number | null;
  per_question_seconds: number | null;
  current_question: QuestionPublic | null;
  finished: boolean;
  score: number;
}

export interface AnswerResult {
  is_correct: boolean;
  correct_option: string;
  explanation: string | null;
  next: QuizAttempt;
}

export interface ResultItem {
  question_id: number;
  question_text: string;
  image_url: string | null;
  selected_option: string;
  correct_option: string;
  is_correct: boolean;
  is_marked: boolean;
  explanation: string | null;
}

export interface PersonalBest {
  is_baseline: boolean;
  is_best: boolean;
  current_pct: number;
  previous_best_pct: number | null;
  /** Percentage POINTS, not percent. 62 -> 74 is +12 points, not +12%. */
  delta_points: number | null;
  attempts: number;
  message: string;
}

export interface QuizResults {
  score: number;
  total: number;
  items: ResultItem[];
  personal_best: PersonalBest | null;
}

export interface TopicStat {
  topic: string;
  subject: string | null;
  correct: number;
  total: number;
  percentage: number;
}

export interface PracticeDay {
  date: string;
  label: string;
  practiced: boolean;
  is_today: boolean;
  is_future: boolean;
}

export interface ScoreEstimate {
  available: boolean;
  projected_low: number | null;
  projected_high: number | null;
  based_on_answers: number;
  message: string | null;
}

export interface Dashboard {
  points: number;
  current_streak: number;
  longest_streak: number;
  streak_freezes: number;
  daily_goal: number;
  points_today: number;
  goal_met: boolean;
  has_taken_diagnostic: boolean;
  topic_stats: TopicStat[];
  review_count: number;
  exam_years: string[];
  recommended_topics: TopicStat[];
  due_for_review_count: number;
  score_estimate: ScoreEstimate;
  practice_days: PracticeDay[];
  blitz_best: number;
  unfinished_attempt: UnfinishedAttempt | null;
  level: Level | null;
  mastery_streak: number;
  longest_mastery_streak: number;
}

export interface Level {
  level: number;
  title: string;
  xp_into_level: number;
  xp_for_next: number;
  percent: number;
}

export interface UnfinishedAttempt {
  id: number;
  mode: string;
  subject: string | null;
  answered: number;
  total: number;
}

export interface TutorAskResponse {
  reply: string;
  queries_remaining_today: number;
}

export interface MockNavItem {
  index: number;
  question_id: number;
  answered: boolean;
  marked: boolean;
}

export interface MockNav {
  items: MockNavItem[];
  finished: boolean;
  time_limit_seconds: number | null;
  started_at: string;
}

export interface MockQuestion {
  index: number;
  total: number;
  question: QuestionPublic;
  selected_option: string | null;
  marked: boolean;
}

export interface SuggestTagsResponse {
  subject: string | null;
  topic: string | null;
  subtopic: string | null;
  difficulty: Difficulty | null;
  note: string | null;
}

export interface Achievement {
  code: string;
  title: string;
  description: string;
  icon: string;
  earned: boolean;
  earned_at: string | null;
  newly_unlocked: boolean;
  progress: number;
  target: number;
}

export interface AchievementsResponse {
  items: Achievement[];
  newly_unlocked: string[];
}

export interface AdminQuestion {
  id: number;
  question_id: string;
  subject: string;
  topic: string;
  subtopic: string | null;
  difficulty: Difficulty;
  exam_type: string | null;
  year: string | null;
  passage_id: string | null;
  question_text: string;
  image_url: string | null;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: string;
  explanation: string | null;
  tags: string | null;
  source: QuestionSource;
  status: QuestionStatus;
}

export interface AdminStats {
  total_questions: number;
  total_users: number;
  subjects: string[];
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  points: number;
  is_admin: boolean;
  current_streak: number;
  longest_streak: number;
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  username: string;
  points: number;
  current_streak: number;
  is_you: boolean;
}

export interface Leaderboard {
  entries: LeaderboardEntry[];
  your_rank: number;
  your_points: number;
}

export interface StudyPlanTask {
  date: string;
  subject: string;
  topic: string | null;
  question_count: number;
}

export interface StudyPlan {
  configured: boolean;
  exam_date: string | null;
  subjects: string[];
  days_until_exam: number | null;
  today: StudyPlanTask | null;
  week: StudyPlanTask[];
}

export interface Flashcard {
  id: number;
  question_text: string;
  image_url: string | null;
  answer_text: string;
  explanation: string | null;
  subject: string | null;
  topic: string;
}

export interface FlashcardsResponse {
  items: Flashcard[];
}

export interface PublicQuestion {
  date: string;
  subject: string | null;
  topic: string;
  question_text: string;
  image_url: string | null;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: string;
  explanation: string | null;
}

export interface TopStudentEntry {
  rank: number;
  username: string;
  points: number;
  current_streak: number;
}

export interface TopStudents {
  entries: TopStudentEntry[];
}

export interface GuestQuestion {
  id: number;
  subject: string;
  topic: string;
  question_text: string;
  image_url: string | null;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: string;
  explanation: string | null;
}

export interface GuestPractice {
  subject: string;
  questions: GuestQuestion[];
}

export interface PremiumStatus {
  is_premium: boolean;
  premium_until: string | null;
  free_mock_exams_remaining: number;
}

export interface PaymentInitialize {
  authorization_url: string;
  reference: string;
}

export interface MyCode {
  code: string;
}

export interface LinkedChild {
  id: number;
  username: string;
  current_streak: number;
  points: number;
  linked_at: string;
}

export interface ChildSummary {
  id: number;
  username: string;
  points: number;
  current_streak: number;
  longest_streak: number;
  topic_stats: TopicStat[];
  recommended_topics: TopicStat[];
  score_estimate: ScoreEstimate;
}

export interface GlossaryTerm {
  term: string;
  definition: string;
}

export interface LessonNote {
  id: number;
  subject: string;
  topic: string;
  title: string;
  summary: string | null;
  glossary: GlossaryTerm[];
  content_md: string;
  related_topics: string[];
  status: string;
  helpful_count: number;
  unhelpful_count: number;
  updated_at: string;
  is_read: boolean;
  my_feedback: boolean | null;
}

export interface NoteStatusItem {
  subject: string;
  topic: string;
  note_id: number | null;
  status: 'missing' | 'draft' | 'active';
  question_count: number;
}

export interface NoteTutorResponse {
  reply: string;
  queries_remaining_today: number;
}

export interface LearnSubjectProgress {
  subject: string;
  total_topics: number;
  read_topics: number;
  percentage: number;
}

export interface LearnHub {
  subjects: LearnSubjectProgress[];
}

export interface QuestTopic {
  topic: string;
  description: string | null;
  estimated_minutes: number;
  // locked | available | learning | practising | proficient | mastered | review_due
  state: string;
  stars: number;
  mastery_score: number;
  prerequisite: string | null;
  can_test_out: boolean;
  next_review_at: string | null;
}

export interface QuestMap {
  subject: string;
  total_topics: number;
  mastered_topics: number;
  review_due_topics: number;
  percent_complete: number;
  recommended_topic: string | null;
  practice_pass_pct: number;
  challenge_pass_pct: number;
  topics: QuestTopic[];
}

export interface DailyMission {
  kind: string; // progress | practice | improvement
  title: string;
  subject: string | null;
  topic: string | null;
  target: number;
  progress: number;
  completed: boolean;
  estimated_minutes: number;
  action_path: string | null;
}

export interface DailyMissions {
  local_date: string;
  items: DailyMission[];
  all_complete: boolean;
  reward_xp: number;
  reward_claimed: boolean;
  total_minutes: number;
}
