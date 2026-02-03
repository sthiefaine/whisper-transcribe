interface ProgressBarProps {
  percent: number;
  phase: string;
  message: string;
  currentChunk: number;
  totalChunks: number;
}

const phaseLabels: Record<string, string> = {
  chunking: 'Preparing audio...',
  transcribing: 'Transcribing',
  diarizing: 'Identifying speakers...',
  merging: 'Finalizing transcript...',
  completed: 'Complete!',
};

export function ProgressBar({
  percent,
  phase,
  message,
  currentChunk,
  totalChunks,
}: ProgressBarProps) {
  const label =
    phase === 'transcribing'
      ? `${phaseLabels[phase]} (${currentChunk}/${totalChunks})`
      : phaseLabels[phase] || phase;

  return (
    <div className="progress-container">
      <div className="progress-header">
        <span className="phase">{label}</span>
        <span className="percent">{Math.round(percent)}%</span>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="progress-message">{message}</div>

      {phase === 'transcribing' && totalChunks > 0 && (
        <div className="chunk-indicators">
          {Array.from({ length: Math.min(totalChunks, 30) }, (_, i) => (
            <div
              key={i}
              className={`chunk-dot ${
                i < currentChunk ? 'completed' : i === currentChunk - 1 ? 'active' : ''
              }`}
              title={`Chunk ${i + 1}`}
            />
          ))}
          {totalChunks > 30 && <span className="more-chunks">+{totalChunks - 30} more</span>}
        </div>
      )}
    </div>
  );
}
