import { useState, useCallback } from 'react';
import { UploadPanel } from './components/UploadPanel';
import { JobList } from './components/JobList';
import { TranscriptViewer } from './components/TranscriptViewer';
import { uploadJob } from './api/client';
import type { UploadOptions } from './types';
import './styles.css';

type View = 'jobs' | 'transcript';

export function App() {
  const [view, setView] = useState<View>('jobs');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUpload = useCallback(async (file: File, options: UploadOptions) => {
    setIsUploading(true);
    setUploadProgress(0);

    try {
      await uploadJob(file, options, setUploadProgress);
      setRefreshTrigger((t) => t + 1);
    } catch (err) {
      console.error('Upload failed:', err);
      alert('Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  }, []);

  const handleViewTranscript = useCallback((jobId: string) => {
    setSelectedJobId(jobId);
    setView('transcript');
  }, []);

  const handleCloseTranscript = useCallback(() => {
    setView('jobs');
    setSelectedJobId(null);
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1>Podcast Transcriber</h1>
        <p className="subtitle">Powered by Voxtral Transcribe 2</p>
      </header>

      <main className="main">
        {view === 'jobs' ? (
          <>
            <UploadPanel
              onUpload={handleUpload}
              isUploading={isUploading}
              uploadProgress={uploadProgress}
            />
            <JobList onViewTranscript={handleViewTranscript} refreshTrigger={refreshTrigger} />
          </>
        ) : (
          selectedJobId && (
            <TranscriptViewer jobId={selectedJobId} onClose={handleCloseTranscript} />
          )
        )}
      </main>

      <footer className="footer">
        <p>Transcription powered by Mistral AI</p>
      </footer>
    </div>
  );
}
