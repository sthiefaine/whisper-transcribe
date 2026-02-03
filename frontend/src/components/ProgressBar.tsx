import { formatTimeRemaining } from '../utils/timeFormatting';

interface ProgressBarProps {
  percent: number;
  phase: string;
  message: string;
  totalEta?: number;
}

const phaseLabels: Record<string, string> = {
  transcribing: 'Transcription (Voxtral)...',
  completed: 'Terminé !',
};

export function ProgressBar({
  percent,
  phase,
  message,
  totalEta,
}: ProgressBarProps) {
  const label = phaseLabels[phase] || phase;
  const isIndeterminate = phase === 'transcribing' && percent > 0 && percent < 95;

  return (
    <div className="progress-container">
      {/* Main progress bar */}
      <div className="progress-bar">
        <div
          className={`progress-fill ${phase} ${isIndeterminate ? 'indeterminate' : ''}`}
          style={{ width: isIndeterminate ? '100%' : `${percent}%` }}
        />
      </div>

      {/* Progress details row */}
      <div className="progress-details">
        <span className="progress-phase">{label}</span>
        {totalEta && totalEta > 0 && (
          <span className="progress-eta">
            ~{formatTimeRemaining(totalEta)} restant
          </span>
        )}
        <span className="progress-percent">{Math.round(percent)}%</span>
      </div>

      {/* Message */}
      {message && <div className="progress-message">{message}</div>}
    </div>
  );
}
