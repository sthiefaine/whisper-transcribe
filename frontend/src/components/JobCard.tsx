import type { Job, ProgressUpdate } from '../types';
import { ProgressBar } from './ProgressBar';

interface JobCardProps {
  job: Job;
  progress: ProgressUpdate | null;
  onView: () => void;
  onResume: () => void;
  onCancel: () => void;
  onDelete: () => void;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}h ${m}m`;
  }
  return `${m}m ${s}s`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleString();
}

const statusColors: Record<string, string> = {
  pending: '#6b7280',
  chunking: '#3b82f6',
  transcribing: '#3b82f6',
  diarizing: '#8b5cf6',
  merging: '#3b82f6',
  processing: '#3b82f6',
  completed: '#10b981',
  failed: '#ef4444',
  cancelled: '#f59e0b',
};

export function JobCard({ job, progress, onView, onResume, onCancel, onDelete }: JobCardProps) {
  const isProcessing = ['pending', 'chunking', 'transcribing', 'diarizing', 'merging', 'processing'].includes(
    job.status
  );
  const canResume = ['failed'].includes(job.status);
  const canCancel = isProcessing;

  return (
    <div className={`job-card ${job.status}`}>
      <div className="job-header">
        <h3 className="job-filename">{job.filename}</h3>
        <span className="job-status" style={{ backgroundColor: statusColors[job.status] }}>
          {job.status}
        </span>
      </div>

      <div className="job-meta">
        <span>{formatFileSize(job.file_size)}</span>
        {job.duration_seconds && <span>{formatDuration(job.duration_seconds)}</span>}
        <span>{job.model_size}</span>
        {job.enable_diarization && <span>+ Diarization</span>}
      </div>

      <div className="job-dates">
        <span>Created: {formatDate(job.created_at)}</span>
        {job.completed_at && <span>Completed: {formatDate(job.completed_at)}</span>}
      </div>

      {isProcessing && progress && (
        <ProgressBar
          percent={progress.percent_complete}
          phase={progress.current_phase}
          message={progress.message}
          currentChunk={progress.current_chunk}
          totalChunks={progress.total_chunks}
        />
      )}

      {job.error_message && <div className="job-error">{job.error_message}</div>}

      <div className="job-actions">
        {job.status === 'completed' && (
          <button className="btn btn-primary" onClick={onView}>
            View Transcript
          </button>
        )}
        {canResume && (
          <button className="btn btn-secondary" onClick={onResume}>
            Resume
          </button>
        )}
        {canCancel && (
          <button className="btn btn-warning" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button className="btn btn-danger" onClick={onDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}
