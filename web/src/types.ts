export type Tone = "info" | "success" | "error";

export type Notice = {
  tone: Tone;
  message: string;
};

export type ApiEnvelope<T> = {
  success: boolean;
  message: string;
  data: T;
};

export type GenerationOptions = {
  emo_alpha?: number;
  emo_vector?: number[];
  emo_text?: string;
  use_emo_text?: boolean;
  text_split_method?: string;
  interval_silence?: number;
  temperature?: number;
  top_p?: number;
  top_k?: number;
  max_mel_tokens?: number;
  repetition_penalty?: number;
  length_penalty?: number;
  num_beams?: number;
  use_random?: boolean;
  max_text_tokens_per_segment?: number;
};

export type HealthPayload = {
  status: string;
};

export type SpeakerProfile = {
  name: string;
  ref_audio: string;
  options: GenerationOptions;
};

export type SpeakerProfilePayload = {
  items: SpeakerProfile[];
};

export type EpisodeConfig = {
  id: string;
  name: string;
  description?: string | null;
};

export type ProjectConfig = {
  id: string;
  name: string;
  description?: string | null;
  episodes: EpisodeConfig[];
  created_at: string;
  updated_at: string;
};

export type ProjectListPayload = {
  items: ProjectConfig[];
};

export type JobSummary = {
  job_id: string;
  status: string;
  script_path: string;
  output_dir: string;
  total: number;
  done: number;
  skipped: number;
  failed: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
};

export type JobListPayload = {
  items: JobSummary[];
};

export type JobLine = {
  line_id: string;
  scene: string | null;
  speaker: string;
  text: string;
  output_name: string | null;
  override: Record<string, unknown>;
  start_ms: number | null;
  end_ms: number | null;
  status: string;
  output_path?: string | null;
  duration_ms: number;
  error?: string | null;
};

export type JobLinesPayload = {
  items: JobLine[];
};

export type SingleResult = {
  status: string;
  speaker: string;
  text: string;
  output_path: string;
  duration_ms: number;
  used_options: Record<string, unknown>;
};

export type InlineLineDraft = {
  id: string;
  scene: string;
  speaker: string;
  text: string;
  outputName: string;
};

export type StudioPageId = "projects" | "roles" | "studio" | "jobs";
