import { useEffect, useState, useCallback } from 'react';
import type { Job } from '../types';
import { listJobs, deleteJob, resumeJob, cancelJob } from '../api/client';
import { useJobProgress } from '../hooks/useWebSocket';
import { JobCard } from './JobCard';

interface JobListProps {
  onViewTranscript: (jobId: string) => void;
  refreshTrigger: number;
}

export function JobList({ onViewTranscript, refreshTrigger }: JobListProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const { progress } = useJobProgress(activeJobId);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(data.jobs);

      // Find active job for WebSocket
      const activeJob = data.jobs.find((j) =>
        ['pending', 'chunking', 'transcribing', 'diarizing', 'merging', 'processing'].includes(j.status)
      );
      setActiveJobId(activeJob?.id || null);

      setError(null);
    } catch (err) {
      setError('Failed to load jobs');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs, refreshTrigger]);

  // Refresh when progress indicates completion
  useEffect(() => {
    if (progress?.status === 'completed') {
      fetchJobs();
    }
  }, [progress?.status, fetchJobs]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleDelete = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this job?')) return;
    try {
      await deleteJob(jobId);
      await fetchJobs();
    } catch (err) {
      console.error('Failed to delete job:', err);
    }
  };

  const handleResume = async (jobId: string) => {
    try {
      await resumeJob(jobId);
      await fetchJobs();
    } catch (err) {
      console.error('Failed to resume job:', err);
    }
  };

  const handleCancel = async (jobId: string) => {
    try {
      await cancelJob(jobId);
      await fetchJobs();
    } catch (err) {
      console.error('Failed to cancel job:', err);
    }
  };

  if (loading) {
    return <div className="loading">Loading jobs...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  if (jobs.length === 0) {
    return <div className="empty">No jobs yet. Upload an audio file to get started.</div>;
  }

  return (
    <div className="job-list">
      <h2>Jobs ({jobs.length})</h2>
      {jobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          progress={job.id === activeJobId ? progress : null}
          onView={() => onViewTranscript(job.id)}
          onResume={() => handleResume(job.id)}
          onCancel={() => handleCancel(job.id)}
          onDelete={() => handleDelete(job.id)}
        />
      ))}
    </div>
  );
}
