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
  /** Null for an unanswered question — running out of time is not a mistake. */
  label: AnswerLabel | null;
  label_title: string | null;
  label_message: string | null;
  label_tone: 'success' | 'neutral' | 'warning' | 'danger' | null;
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
  quality: AnswerQuality | null;
  subject: string | null;
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

export interface LeagueEntry {
  rank: number;
  /** Self-chosen username only — never email, school or location. */
  username: string;
  points: number;
  is_you: boolean;
  zone: 'promotion' | 'safe' | 'demotion';
}

export interface League {
  opted_out: boolean;
  tier: string;
  tier_label: string;
  week_start: string;
  days_remaining: number;
  your_rank: number | null;
  your_points: number;
  entries: LeagueEntry[];
  promote_top: number;
  demote_bottom: number;
}

export interface BattleQuestion {
  id: number;
  question_text: string;
  image_url: string | null;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
}

export interface Battle {
  code: string;
  subject: string;
  topic: string | null;
  questions: number;
  seconds_per_question: number;
  status: string;
  expires_at: string;
  players: number;
  you_submitted: boolean;
  mode: string;
  started_at: string | null;
}

export interface BattleSide {
  /** Always sent, never inferred from the name. */
  is_bot?: boolean;
  bot_blurb?: string | null;
  username: string;
  score: number;
  attempted: number;
  submitted: boolean;
  avg_correct_seconds: number | null;
}

export interface BattleReviewItem {
  question_id: number;
  question_text: string;
  correct_option: string;
  your_answer: string;
  explanation: string | null;
}

export interface BattleResult {
  code: string;
  subject: string;
  status: string;
  mode: string;
  outcome: 'waiting' | 'won' | 'lost' | 'draw';
  you: BattleSide;
  opponent: BattleSide | null;
  review: BattleReviewItem[];
  /** A practice-bot result. Never counts toward leagues or leaderboards. */
  vs_bot?: boolean;
}

export interface BattleLive {
  code: string;
  started: boolean;
  current_index: number | null;
  /** Select the question by THIS, never by indexing at current_index. */
  current_question_id: number | null;
  seconds_remaining: number | null;
  total: number;
  finished: boolean;
  you_answered: number;
  opponent_answered: number;
  /** Presentational only — a dropped connection never forfeits a battle. */
  opponent_present: boolean;
}

/** One question a day, the same one for every student. */
export interface DailyQuestion {
  date: string;
  question_id: number;
  subject: string | null;
  topic: string;
  question_text: string;
  image_url: string | null;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;

  answered: boolean;
  your_answer: string | null;
  your_seconds: number | null;
  is_correct: boolean | null;
  /** Null until this student has answered — the API withholds it deliberately. */
  correct_option: string | null;
  explanation: string | null;

  answered_count: number;
  percent_correct: number | null;
  average_seconds: number | null;
  streak: number;
}

export interface DailyQuestionResult {
  is_correct: boolean;
  correct_option: string;
  explanation: string | null;
  your_seconds: number | null;
  answered_count: number;
  percent_correct: number | null;
  average_seconds: number | null;
  /** Null until enough students have answered for the comparison to mean anything. */
  faster_than_percent: number | null;
  streak: number;
}

/** Named mistake type for one answer. See backend/app/answer_labels.py. */
export type AnswerLabel = 'sharp' | 'solid' | 'lucky' | 'slip' | 'gap' | 'blunder';

export interface AnswerQuality {
  /** Weighted, so a lucky guess does not read the same as a clean answer. */
  accuracy: number | null;
  counts: Partial<Record<AnswerLabel, number>>;
  headline: string | null;
  focus_topics: string[];
}

/**
 * Predicted exam score for one subject.
 *
 * Note what is absent: the raw Glicko rating. It stays server-side on
 * purpose — "I'm a 900 and my friend is a 1400" is the damage this framing
 * exists to avoid.
 */
export interface SubjectRating {
  subject: string;
  predicted_score: number;
  range_low: number;
  range_high: number;
  provisional: boolean;
  answers_counted: number;
  /** Only rendered when positive; a fall is never announced on its own. */
  week_delta: number | null;
}

export interface RushState {
  attempt_id: number;
  score: number;
  strikes: number;
  strikes_allowed: number;
  finished: boolean;
  personal_best: number;
}

export interface PracticeBot {
  key: string;
  name: string;
  rating: number;
  blurb: string;
  is_bot: true;
}

/** A flat, actionable statement about the student's own data. */
export interface Insight {
  key: string;
  icon: string;
  text: string;
  action_label: string | null;
  action_href: string | null;
}

export interface School {
  id: number;
  slug: string;
  name: string;
  state: string | null;
  /** community | claimed | verified — a student typing a name is only a claim. */
  status: string;
}

export interface SchoolLeaderboardEntry {
  rank: number;
  school_id: number;
  slug: string;
  name: string;
  state: string | null;
  status: string;
  total_points: number;
  active_members: number;
  /** The ranked figure — normalised so the table is not a size ranking. */
  points_per_member: number;
}

export interface MySchool {
  school: School;
  total_points: number;
  active_members: number;
  points_per_member: number;
  /** The only individual figure in the schools API, and only ever your own. */
  your_contribution: number;
  state_rank: number | null;
  national_rank: number | null;
  last_week_national_rank: number | null;
  can_change_after: string | null;
}

/** One weekly signup cohort. Null retention = too young to know yet. */
export interface Cohort {
  week_start: string;
  signups: number;
  activated: number;
  d1: number | null;
  d7: number | null;
  d14: number | null;
}

export interface AnalyticsFunnel {
  signups: number;
  answered_one: number;
  answered_ten: number;
  completed_attempt: number;
  median_seconds_to_first_question: number | null;
  within_target_pct: number | null;
}

export interface Analytics {
  /** The single number a teacher trial exists to produce. */
  week_two_return_pct: number | null;
  cohorts_measured: number;
  students_measured: number;
  time_to_value_target_seconds: number;
  cohorts: Cohort[];
  funnel: AnalyticsFunnel;
  daily: { date: string; signups: number; activated: number }[];
}
