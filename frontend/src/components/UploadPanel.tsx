import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import type { UploadOptions } from '../types';

interface UploadPanelProps {
  onUpload: (file: File, options: UploadOptions) => Promise<void>;
  isUploading: boolean;
  uploadProgress: number;
}

const LANGUAGES = [
  { code: '', name: 'Auto-detect' },
  { code: 'en', name: 'English' },
  { code: 'fr', name: 'French' },
  { code: 'es', name: 'Spanish' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'nl', name: 'Dutch' },
  { code: 'pl', name: 'Polish' },
  { code: 'ru', name: 'Russian' },
  { code: 'ja', name: 'Japanese' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ko', name: 'Korean' },
  { code: 'ar', name: 'Arabic' },
];

export function UploadPanel({ onUpload, isUploading, uploadProgress }: UploadPanelProps) {
  const [options, setOptions] = useState<UploadOptions>({
    language: null,
    enable_diarization: true,
    num_speakers: null,
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0 || isUploading) return;
      await onUpload(acceptedFiles[0], options);
    },
    [onUpload, options, isUploading]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac'],
    },
    maxFiles: 1,
    disabled: isUploading,
  });

  return (
    <div className="upload-panel">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''} ${isUploading ? 'uploading' : ''}`}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <div className="upload-progress">
            <p>Uploading... {uploadProgress}%</p>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        ) : isDragActive ? (
          <p>Drop the audio file here...</p>
        ) : (
          <div>
            <p>Drag and drop an audio file here</p>
            <p className="hint">or click to select a file</p>
            <p className="formats">MP3, WAV, M4A, FLAC, OGG supported (up to 1GB)</p>
          </div>
        )}
      </div>

      <div className="options">
        <div className="option-group">
          <label>
            Language:
            <select
              value={options.language || ''}
              onChange={(e) => setOptions({ ...options, language: e.target.value || null })}
              disabled={isUploading}
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="option-group info">
          <span className="engine-badge">Voxtral Transcribe 2</span>
        </div>

        <div className="option-group checkbox">
          <label>
            <input
              type="checkbox"
              checked={options.enable_diarization}
              onChange={(e) => setOptions({ ...options, enable_diarization: e.target.checked })}
              disabled={isUploading}
            />
            Enable speaker identification
          </label>
        </div>

        {options.enable_diarization && (
          <div className="option-group">
            <label>
              Number of speakers:
              <input
                type="number"
                min="1"
                max="20"
                value={options.num_speakers || ''}
                onChange={(e) =>
                  setOptions({
                    ...options,
                    num_speakers: e.target.value ? parseInt(e.target.value) : null,
                  })
                }
                placeholder="Auto-detect"
                disabled={isUploading}
              />
            </label>
          </div>
        )}
      </div>
    </div>
  );
}
