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

// Languages an answer can be shown in: "en" is the original answer, the other two are
// generated on request (or automatically, per the user's preference).
export type ExplainLanguage = "ur" | "roman_ur";
export type AppLanguage = "en" | ExplainLanguage;
export type ExplainMode = "translate" | "simplify";

export interface MessageTranslation {
  language: ExplainLanguage;
  mode: ExplainMode;
  text: string;
  fidelity_warning: boolean;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[] | null;
  created_at: string;
  followUps?: string[];
  content_type?: string;
  translations?: MessageTranslation[];
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

// ---- Revision sheets ----------------------------------------------------------------------

export type SheetLanguage = "en" | "ur" | "roman_ur" | "bilingual";
export type SheetStatus = "queued" | "generating" | "ready" | "failed";

export interface RevisionSheetListItem {
  id: string;
  title: string;
  status: SheetStatus;
  language: SheetLanguage;
  page_target: number;
  created_at: string;
}

export interface RevisionSheetItem {
  id: string;
  kind: "definition" | "formula" | "fact" | "key_point" | "process" | "watch_out";
  rank: number;
  ref: string; // "p.12", "14:32", or "D2 p.12" when several documents are mixed
  doc_id: string;
  page: number | null;
  t: number | null;
  term?: string;
  definition?: string;
  name?: string;
  expression?: string;
  when_to_use?: string;
  fact?: string;
  topic?: string;
  point?: string;
  steps?: string[];
  gloss?: string; // Urdu line shown under the English text in bilingual sheets
}

export interface RevisionSheetContent {
  title: string;
  subtitle: string;
  language: SheetLanguage;
  page_target: number;
  labels: Record<string, string>;
  labels_ur?: Record<string, string>;
  sections: { type: string; items: RevisionSheetItem[] }[];
  self_check: { question: string; answer: string; ref: string }[];
  sources: { tag: string; document: string; document_id: string; refs: string[] }[];
  warnings: string[];
  pages?: number;
  dropped_items?: number;
}

export interface RevisionSheetDetail {
  id: string;
  title: string;
  status: SheetStatus;
  language: SheetLanguage;
  page_target: number;
  include_weak_spots: boolean;
  topics: string[] | null;
  document_ids: string[];
  workspace_id: string | null;
  content: RevisionSheetContent | null;
  error_message: string | null;
  created_at: string;
}

// ---- Tutor Mode ---------------------------------------------------------------------------

export type TutorLevel = "beginner" | "intermediate" | "exam_ready";
export type TutorLanguage = "en" | "ur" | "roman_ur";

export interface TutorSourceRef {
  document_id: string | null;
  filename: string | null;
  page_number: number | null;
  start_time_seconds: number | null;
}

export interface TutorTurn {
  id: string;
  step_index: number;
  role: "tutor" | "student";
  content: string;
  turn_type: string | null;
  hint_level: number | null;
  verdict: "correct" | "partial" | "incorrect" | "skipped" | null;
  source_refs: TutorSourceRef[] | null;
  created_at: string;
}

export interface TutorConceptProgress {
  index: number;
  name: string;
  phase: string;
  mastered: boolean;
  revealed: boolean;
  attempts: number;
  hints_used: number;
}

export interface TutorProgress {
  concept_index: number;
  total_concepts: number;
  mastered_count: number;
  revealed_count: number;
  hint_level: number;
  phase: string;
  concepts: TutorConceptProgress[];
}

export interface TutorSummary {
  strengths: string[];
  needs_work: { concept: string; why: string; source_refs: TutorSourceRef[] }[];
  next_steps: string[];
  cards_added?: number;
  mastered_count?: number;
  total_concepts?: number;
}

export interface TutorSession {
  id: string;
  title: string;
  topic: string;
  level: TutorLevel;
  language: TutorLanguage;
  status: "active" | "completed" | "abandoned";
  turn_count: number;
  max_turns: number;
  document_ids: string[];
  workspace_id: string | null;
  created_at: string;
  completed_at: string | null;
  summary: TutorSummary | null;
  progress: TutorProgress;
  finished: boolean;
  turns: TutorTurn[];
}

export interface TutorSessionListItem {
  id: string;
  title: string;
  topic: string;
  level: TutorLevel;
  status: "active" | "completed" | "abandoned";
  turn_count: number;
  mastered_count: number;
  total_concepts: number;
  created_at: string;
}
