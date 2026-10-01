/** Types mirroring the backend's pydantic schemas. */

export type Difficulty = "easy" | "medium" | "hard";
export type InterviewLength = 5 | 8 | 12;
export type TurnKind = "opener" | "question" | "follow_up" | "closing" | "answer";

export interface RepoMeta {
  owner: string;
  name: string;
  full_name: string;
  description: string;
  default_branch: string;
  sha: string;
  stars: number;
  language: string | null;
  html_url: string;
  total_files: number;
  tree_truncated: boolean;
}

export interface IngestResponse {
  repo_id: string;
  repo_meta: RepoMeta;
  files_analyzed: string[];
  dependencies: string[];
}

export interface TechItem {
  name: string;
  purpose: string;
  evidence_files: string[];
}

export interface CandidateQuestion {
  topic: string;
  difficulty: number;
  question: string;
  what_good_answer_covers: string[];
  related_files: string[];
}

export interface Dossier {
  summary: string;
  tech_stack: TechItem[];
  architecture: {
    components: { name: string; responsibility: string; files: string[] }[];
    data_flow: string;
  };
  key_design_decisions: { decision: string; rationale: string; files: string[] }[];
  likely_weak_spots: { area: string; description: string; files: string[] }[];
  candidate_questions: CandidateQuestion[];
}

export interface DossierResponse {
  repo_id: string;
  repo_meta: RepoMeta;
  dossier: Dossier;
}

export interface Turn {
  speaker: "interviewer" | "candidate";
  kind: TurnKind;
  text: string;
  question_index: number;
}

export interface TurnOut {
  text: string;
  kind: TurnKind;
  question_number: number;
  total_questions: number;
  topic: string;
}

export interface SessionResponse {
  session_id: string;
  repo_meta: RepoMeta;
  first_turn: TurnOut;
}

export interface SessionState {
  session_id: string;
  repo_meta: RepoMeta;
  length: InterviewLength;
  difficulty: Difficulty;
  transcript: Turn[];
  current_turn: TurnOut | null;
  done: boolean;
}

export interface AnswerResponse {
  next_turn: TurnOut;
  done: boolean;
}

export interface TranscriptionResponse {
  text: string;
}
