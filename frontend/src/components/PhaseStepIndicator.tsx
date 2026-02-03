import React from 'react';

interface PhaseStepIndicatorProps {
  currentPhase: string;
  percentComplete: number;
}

const PhaseStepIndicator: React.FC<PhaseStepIndicatorProps> = ({
  currentPhase,
  percentComplete
}) => {
  const isCompleted = currentPhase === 'completed' || percentComplete >= 100;
  const isTranscribing = currentPhase === 'transcribing';

  return (
    <div className="phase-steps">
      <div className={`phase-step ${isTranscribing ? 'active' : isCompleted ? 'completed' : 'pending'}`}>
        <div className="phase-step-icon">
          {isCompleted ? <span>✓</span> : <span>1</span>}
        </div>
        <div className="phase-step-label">Transcription</div>
        <div className={`phase-step-connector ${isCompleted ? 'completed' : ''}`} />
      </div>
      <div className={`phase-step ${isCompleted ? 'completed' : 'pending'}`}>
        <div className="phase-step-icon">
          {isCompleted ? <span>✓</span> : <span>2</span>}
        </div>
        <div className="phase-step-label">Terminé</div>
      </div>
    </div>
  );
};

export default PhaseStepIndicator;
