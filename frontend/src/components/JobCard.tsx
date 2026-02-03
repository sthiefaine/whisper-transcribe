import type { Job, ProgressUpdate } from '../types';
import { ProgressBar } from './ProgressBar';

interface JobCardProps {
  job: Job;
  progress: ProgressUpdate | null;
  onView: () => void;
  onRetry: () => void;
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
  transcribing: '#3b82f6',
  completed: '#10b981',
  failed: '#ef4444',
  cancelled: '#f59e0b',
};

export function JobCard({ job, progress, onView, onRetry, onCancel, onDelete }: JobCardProps) {
  const isProcessing = ['pending', 'transcribing'].includes(job.status);
  const canRetry = job.status === 'failed';
  const canCancel = isProcessing;

  return (
    <div className={`job-card ${job.status}`}>
      <div className="job-header">
        <h3 className="job-filename">{job.filename}</h3>
        <span className="job-status" style={{ backgroundColor: statusColors[job.status] || '#6b7280' }}>
          {job.status}
        </span>
      </div>

      <div className="job-meta">
        <span>{formatFileSize(job.file_size)}</span>
        {job.duration_seconds && <span>{formatDuration(job.duration_seconds)}</span>}
        <span className="engine-badge-small">Voxtral</span>
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
          totalEta={progress.total_eta_seconds}
        />
      )}

      {job.error_message && <div className="job-error">{job.error_message}</div>}

      <div className="job-actions">
        {job.status === 'completed' && (
          <button className="btn btn-primary" onClick={onView}>
            View Transcript
          </button>
        )}
        {canRetry && (
          <button className="btn btn-secondary" onClick={onRetry}>
            Retry
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
