import { useEffect, useState, useMemo } from 'react';
import type { Transcript, TranscriptSegment } from '../types';
import { getTranscript, getDownloadUrl } from '../api/client';

interface TranscriptViewerProps {
  jobId: string;
  onClose: () => void;
}

const speakerColors: Record<string, string> = {
  SPEAKER_00: '#3b82f6',
  SPEAKER_01: '#10b981',
  SPEAKER_02: '#f59e0b',
  SPEAKER_03: '#ef4444',
  SPEAKER_04: '#8b5cf6',
  SPEAKER_05: '#ec4899',
  SPEAKER_06: '#14b8a6',
  SPEAKER_07: '#f97316',
};

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function getSpeakerColor(speaker: string): string {
  return speakerColors[speaker] || '#6b7280';
}

export function TranscriptViewer({ jobId, onClose }: TranscriptViewerProps) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTranscript() {
      try {
        const data = await getTranscript(jobId);
        setTranscript(data);
        setError(null);
      } catch (err) {
        setError('Failed to load transcript');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadTranscript();
  }, [jobId]);

  // Group segments by speaker for better readability
  const groupedSegments = useMemo(() => {
    if (!transcript) return [];

    const groups: Array<{
      speaker: string;
      segments: TranscriptSegment[];
    }> = [];

    let currentGroup: (typeof groups)[0] | null = null;

    for (const seg of transcript.segments) {
      const speaker = seg.speaker || 'Speaker';

      if (!currentGroup || currentGroup.speaker !== speaker) {
        currentGroup = { speaker, segments: [] };
        groups.push(currentGroup);
      }

      currentGroup.segments.push(seg);
    }

    return groups;
  }, [transcript]);

  const handleDownload = (format: 'txt' | 'srt' | 'vtt' | 'json') => {
    window.open(getDownloadUrl(jobId, format), '_blank');
  };

  if (loading) {
    return (
      <div className="transcript-viewer">
        <div className="transcript-loading">Loading transcript...</div>
      </div>
    );
  }

  if (error || !transcript) {
    return (
      <div className="transcript-viewer">
        <div className="transcript-error">{error || 'Transcript not found'}</div>
        <button className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    );
  }

  return (
    <div className="transcript-viewer">
      <div className="transcript-header">
        <button className="btn btn-back" onClick={onClose}>
          &larr; Back to Jobs
        </button>

        <div className="stats">
          <span>{transcript.word_count} words</span>
          <span>{formatTime(transcript.duration_seconds)} duration</span>
          {transcript.num_speakers && <span>{transcript.num_speakers} speakers</span>}
          <span>Language: {transcript.language}</span>
        </div>

        <div className="download-buttons">
          <button className="btn btn-small" onClick={() => handleDownload('txt')}>
            TXT
          </button>
          <button className="btn btn-small" onClick={() => handleDownload('srt')}>
            SRT
          </button>
          <button className="btn btn-small" onClick={() => handleDownload('vtt')}>
            VTT
          </button>
          <button className="btn btn-small" onClick={() => handleDownload('json')}>
            JSON
          </button>
        </div>
      </div>

      <div className="transcript-content">
        {groupedSegments.map((group, i) => (
          <div key={i} className="speaker-group">
            <div
              className="speaker-label"
              style={{ backgroundColor: getSpeakerColor(group.speaker) }}
            >
              {group.speaker.replace('SPEAKER_', 'Speaker ')}
            </div>

            <div className="speaker-text">
              {group.segments.map((seg, j) => (
                <span key={j} className="segment">
                  <span className="timestamp">[{formatTime(seg.start)}]</span> {seg.text}{' '}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
