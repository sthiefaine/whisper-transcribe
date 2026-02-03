export interface Job {
  id: string;
  filename: string;
  original_path: string;
  file_size: number;
  duration_seconds: number | null;
  status: 'pending' | 'chunking' | 'transcribing' | 'diarizing' | 'merging' | 'completed' | 'failed' | 'cancelled' | 'processing';
  model_size: string;
  language: string | null;
  enable_diarization: boolean;
  num_speakers: number | null;
  total_chunks: number;
  completed_chunks: number;
  current_chunk: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  speaker?: string;
  words?: Array<{
    word: string;
    start: number;
    end: number;
    probability: number;
  }>;
}

export interface Transcript {
  job_id: string;
  full_text: string;
  segments: TranscriptSegment[];
  language: string;
  language_probability: number;
  num_speakers: number | null;
  word_count: number;
  duration_seconds: number;
}

export interface ProgressUpdate {
  type: 'progress';
  job_id: string;
  status: string;
  current_chunk: number;
  total_chunks: number;
  percent_complete: number;
  current_phase: string;
  message: string;
}

export interface UploadOptions {
  language: string | null;
  model_size: string;
  enable_diarization: boolean;
  num_speakers: number | null;
}

export interface Model {
  id: string;
  name: string;
  description: string;
}
