import axios from 'axios';
import type { Job, Transcript, Model, UploadOptions } from '../types';

const api = axios.create({
  baseURL: '/api',
});

export async function uploadJob(
  file: File,
  options: UploadOptions,
  onProgress?: (percent: number) => void
): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('enable_diarization', String(options.enable_diarization));
  if (options.language) {
    formData.append('language', options.language);
  }
  if (options.num_speakers) {
    formData.append('num_speakers', String(options.num_speakers));
  }

  const response = await api.post('/jobs', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });

  return response.data;
}

export async function listJobs(status?: string): Promise<{ jobs: Job[]; count: number }> {
  const params = status ? { status } : {};
  const response = await api.get('/jobs', { params });
  return response.data;
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await api.get(`/jobs/${jobId}`);
  return response.data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await api.delete(`/jobs/${jobId}`);
}

export async function retryJob(jobId: string): Promise<void> {
  await api.post(`/jobs/${jobId}/retry`);
}

export async function cancelJob(jobId: string): Promise<void> {
  await api.post(`/jobs/${jobId}/cancel`);
}

export async function getTranscript(jobId: string): Promise<Transcript> {
  const response = await api.get(`/jobs/${jobId}/transcript`);
  return response.data;
}

export function getDownloadUrl(jobId: string, format: 'txt' | 'srt' | 'vtt' | 'json'): string {
  return `/api/jobs/${jobId}/transcript/download?format=${format}`;
}

export async function getModels(): Promise<{ models: Model[]; default: string }> {
  const response = await api.get('/models');
  return response.data;
}

export async function getSystemStatus(): Promise<{
  active_jobs: number;
  active_job_ids: string[];
}> {
  const response = await api.get('/system/status');
  return response.data;
}
