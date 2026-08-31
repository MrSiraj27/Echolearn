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
