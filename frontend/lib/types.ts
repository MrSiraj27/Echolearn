export type DocumentStatus = "uploaded" | "parsing" | "embedded" | "ready" | "failed";

export const AUDIO_VIDEO_EXTENSIONS = new Set(["mp3", "wav", "m4a", "mp4", "mov"]);
export const VIDEO_EXTENSIONS = new Set(["mp4", "mov"]);

export interface DocumentItem {
  id: string;
  filename: string;
  file_type: string;
  status: DocumentStatus;
  created_at: string;
  summary?: string | null;
  suggested_questions?: string[] | null;
  folder_id?: string | null;
}

export interface Folder {
  id: string;
  name: string;
  created_at: string;
  document_count: number;
}

export interface Workspace {
  id: string;
  name: string;
  created_at: string;
  document_count: number;
}

export interface WorkspaceDetail {
  id: string;
  name: string;
  created_at: string;
  document_ids: string[];
}

export interface ChatItem {
  id: string;
  title: string | null;
  created_at: string;
  preview: string | null;
}

export type MessageRole = "user" | "assistant";

export interface Citation {
  filename: string | null;
  page_number: number | null;
  document_id: string | null;
  chunk_text?: string | null;
  start_time_seconds?: number | null;
}

export type QuestionType = "multiple_choice" | "short_answer";

export interface QuizQuestion {
  id: string;
  question: string;
  type: QuestionType;
  options: string[];
}

export interface QuizDetail {
  id: string;
  title: string;
  document_ids: string[];
  questions: QuizQuestion[];
  created_at: string;
}

export interface QuizListItem {
  id: string;
  title: string;
  question_count: number;
  created_at: string;
  best_score: number | null;
  attempt_count: number;
}

export interface QuestionResult {
  id: string;
  question: string;
  type: QuestionType;
  options: string[];
  submitted_answer: string | null;
  correct_answer: string;
  is_correct: boolean;
  explanation: string;
  source_page: number | null;
  source_filename: string | null;
}

export interface SubmitQuizResponse {
  attempt_id: string;
  score: number;
  total: number;
  correct_count: number;
  results: QuestionResult[];
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[] | null;
  created_at: string;
  followUps?: string[];
  content_type?: string;
}

export type InfographicTemplate = "stats" | "timeline" | "comparison" | "summary";

export interface StatItem {
  label: string;
  value: string;
  icon_hint: string;
}
export interface StatsData {
  title: string;
  subtitle: string;
  stats: StatItem[];
  takeaway: string;
}

export interface TimelineEvent {
  date_or_stage: string;
  label: string;
  description: string;
}
export interface TimelineData {
  title: string;
  events: TimelineEvent[];
}

export interface ComparisonRow {
  aspect: string;
  item_a_value: string;
  item_b_value: string;
}
export interface ComparisonData {
  title: string;
  item_a_name: string;
  item_b_name: string;
  rows: ComparisonRow[];
  verdict?: string;
}

export interface KeyPoint {
  heading: string;
  detail: string;
}
export interface SummaryData {
  title: string;
  key_points: KeyPoint[];
  takeaway: string;
}

export interface InfographicPayload {
  template: InfographicTemplate;
  data: StatsData | TimelineData | ComparisonData | SummaryData;
}

export interface QuestionsOverTimePoint {
  date: string;
  count: number;
}

export interface AnalyticsOverview {
  total_questions_asked: number;
  total_documents: number;
  total_quizzes_taken: number;
  avg_quiz_score: number | null;
  most_active_document: string | null;
  questions_over_time: QuestionsOverTimePoint[];
}

export interface KnowledgeGapTheme {
  theme: string;
  count: number;
  example_questions: string[];
}

export interface DocumentPerformanceItem {
  document_id: string;
  filename: string;
  times_referenced: number;
  times_not_found: number;
  quiz_avg_score: number | null;
}

export interface QuizInsightQuestion {
  quiz_id: string;
  quiz_title: string;
  question_id: string;
  question: string;
  times_wrong: number;
  times_attempted: number;
  wrong_rate: number;
}

// ---- Daily Review / SM-2 (Prompt 30) ----

export type ReviewQuestionType = "multiple_choice" | "short_answer" | "true_false";

export interface ReviewCardWithState {
  id: string;
  document_id: string;
  question: string;
  answer: string;
  question_type: ReviewQuestionType;
  options: string[] | null;
  source_chunk_id: string | null;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
  next_review_date: string;
}

export interface TodayReviewResponse {
  cards: ReviewCardWithState[];
  total_due: number;
  capped_at: number;
}

export interface SubmitReviewResponse {
  next_review_date: string;
  interval_days: number;
}

export interface ReviewStatsResponse {
  current_streak_days: number;
  total_cards: number;
  cards_mastered: number;
  cards_struggling: number;
}

export interface ReviewSettingsResponse {
  daily_cap: number;
}

// ---- Study Planner (Prompt 29) ----

export type StudySessionType = "learn" | "review" | "quiz" | "checkpoint";
export type StudySessionStatus = "pending" | "completed" | "skipped";
export type StudyPlanStatus = "active" | "completed" | "abandoned";

export interface TopicPreview {
  title: string;
  description: string;
  estimated_difficulty: "easy" | "medium" | "hard";
}

export interface SessionPreview {
  scheduled_date: string;
  topic_title: string;
  topic_description: string;
  session_type: StudySessionType;
}

export interface PlanWarning {
  warning: string;
  suggested_reduced_topics: string[];
}

export interface PreviewStudyPlanResponse {
  plan_token: string;
  topics: TopicPreview[];
  sessions: SessionPreview[];
  warning: PlanWarning | null;
}

export interface StudySessionPublic {
  id: string;
  scheduled_date: string;
  topic_title: string;
  topic_description: string;
  session_type: StudySessionType;
  status: StudySessionStatus;
  completed_at: string | null;
  quiz_id: string | null;
}

export interface StudyPlanResponse {
  id: string;
  title: string;
  exam_date: string;
  document_ids: string[] | null;
  workspace_id: string | null;
  daily_study_minutes: number;
  status: StudyPlanStatus;
  created_at: string;
  session_count: number;
  completed_count: number;
}

export interface StudyPlanDetailResponse extends StudyPlanResponse {
  sessions: StudySessionPublic[];
}

export interface TodaySessionItem {
  plan_id: string;
  plan_title: string;
  session: StudySessionPublic;
}

export interface PlanStatusResponse {
  status: "on_track" | "slightly_behind" | "significantly_behind";
  completed_count: number;
  expected_by_now_count: number;
  total_count: number;
}

export interface PracticeQuestion {
  id: string;
  question: string;
  type: "multiple_choice" | "short_answer";
  options: string[];
  correct_answer: string;
  explanation: string;
}

export interface SessionContentResponse {
  topic_title: string;
  topic_description: string;
  session_type: StudySessionType;
  explanation: string;
  practice_questions: PracticeQuestion[];
}

// ---- Practice Papers (AI-generated practice exams) ----

export type PracticeQuestionType =
  | "multiple_choice"
  | "short_answer"
  | "long_answer"
  | "numerical"
  | "diagram_based";

export type PatternSource = "custom" | "past_papers" | "standard";

export interface PaperSectionConfig {
  name: string;
  question_type: PracticeQuestionType;
  count: number;
  marks_each: number;
}

export interface PaperPatternConfig {
  sections: PaperSectionConfig[];
  total_marks: number;
  total_questions: number;
}

export interface ExtractedPastPaperPattern extends PaperPatternConfig {
  recurring_topics_mentioned: string[];
}

export interface PastPaperItem {
  id: string;
  document_id: string;
  filename: string;
  exam_name: string | null;
  analysis_status: "pending" | "analyzing" | "ready" | "failed";
  error_message: string | null;
  extracted_pattern: ExtractedPastPaperPattern | null;
  pattern_summary: string | null;
  created_at: string;
}

export interface PastPaperStatus {
  id: string;
  analysis_status: PastPaperItem["analysis_status"];
  document_status: string | null;
  error_message: string | null;
  extracted_pattern: ExtractedPastPaperPattern | null;
  pattern_summary: string | null;
}

export interface PreviewPatternResponse {
  pattern_config: PaperPatternConfig;
  pattern_source: PatternSource;
  pattern_note: string;
  estimated_time_minutes: number;
  recurring_topics: string[];
  past_paper_summary: string | null;
  section_confidence: string[] | null;
}

export interface PracticePaperListItem {
  id: string;
  title: string;
  status: "generating" | "ready" | "failed";
  pattern_source: PatternSource;
  pattern_note: string | null;
  total_marks: number | null;
  total_questions: number | null;
  time_allowed_minutes: number | null;
  error_message: string | null;
  created_at: string;
}

export interface PracticePaperStatusResponse {
  id: string;
  status: "generating" | "ready" | "failed";
  error_message: string | null;
}

export interface PaperSourceReference {
  document_id: string | null;
  filename: string | null;
  page: number | null;
  start_seconds: number | null;
  end_seconds: number | null;
  label: string;
}

export interface PaperQuestion {
  id: string;
  question_type: PracticeQuestionType;
  question_text: string;
  options: string[];
  marks: number;
  topic: string | null;
  topic_reason: string | null;
  source_reference: PaperSourceReference | null;
  source_references: PaperSourceReference[];
}

export interface PaperSection {
  name: string;
  question_type: PracticeQuestionType;
  count: number;
  marks_each: number;
  instructions: string;
  questions: PaperQuestion[];
}

export interface TopicCoverage {
  topic: string;
  origin: "user_important" | "past_paper_pattern";
  found_in_materials: boolean;
  questions_covering: number;
}

export interface PracticePaperDetail {
  id: string;
  title: string;
  status: string;
  disclaimer: string;
  pattern_source: PatternSource;
  pattern_note: string | null;
  pattern_config: PaperPatternConfig;
  time_allowed_minutes: number | null;
  time_estimated: boolean;
  total_marks: number | null;
  total_questions: number | null;
  important_topics: string[] | null;
  topic_coverage: TopicCoverage[];
  sections: PaperSection[];
  created_at: string;
}

export type PaperResultStatus =
  | "correct"
  | "incorrect"
  | "unanswered"
  | "needs_self_grade"
  | "self_graded";

export interface PaperQuestionResult {
  id: string;
  section: string;
  question_type: PracticeQuestionType;
  question_text: string;
  options: string[];
  marks: number;
  submitted_answer: string | null;
  correct_answer: string | null;
  correct_option: string | null;
  model_answer: string | null;
  status: PaperResultStatus;
  marks_awarded: number | null;
  note: string | null;
  source_reference: PaperSourceReference | null;
}

export interface PaperAttemptResult {
  attempt_id: string;
  marks_obtained: number;
  total_marks: number;
  score_percent: number;
  pending_self_grade_count: number;
  results: PaperQuestionResult[];
}
