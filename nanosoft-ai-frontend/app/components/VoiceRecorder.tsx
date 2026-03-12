"use client";

import { useState, useRef, useEffect } from "react";
import { IconMicrophone, IconSend, IconTrash, IconPlayerPlay, IconPlayerPause } from "@tabler/icons-react";

export interface UseVoiceRecorderReturn {
  // States
  isRecording: boolean;
  recordingTime: number;
  recordedAudioBlob: Blob | null;
  isPlaying: boolean;
  playbackTime: number;
  audioDuration: number;
  closingRecording: boolean;
  
  // Handlers
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  toggleRecording: () => Promise<void>;
  cancelRecording: () => void;
  deleteRecording: () => void;
  togglePlayback: () => void;
  sendVoiceMessage: () => Promise<void>;
  
  // Refs
  micButtonRef: React.MutableRefObject<HTMLButtonElement | null>;
  audioPlaybackRef: React.MutableRefObject<HTMLAudioElement | null>;
  
  // UI Helpers
  formatTime: (seconds: number) => string;
  totalDuration: number;
  displayTimeText: string;
}

// ─── Custom Hook: useVoiceRecorder ─────────────────────────────────────────
export function useVoiceRecorder(
  isLoading: boolean,
  wsConnectionState: string,
  loggedInUser: string,
  sessionId: string,
  wsRef: React.MutableRefObject<WebSocket | null>,
  onVoiceMessageSent?: (duration: number, audioUrl: string) => void
): UseVoiceRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordedAudioBlob, setRecordedAudioBlob] = useState<Blob | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [closingRecording, setClosingRecording] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const micButtonRef = useRef<HTMLButtonElement>(null);

  // ── FIX BUG 4: audioPlaybackRef is always wiped on new recording ──────────
  // We keep ONE ref for the preview audio element.
  // It is set to null whenever a new blob is ready, so togglePlayback creates a fresh Audio.
  const audioPlaybackRef = useRef<HTMLAudioElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);   // ← tracks rAF for cancel

  const recordingStartTimeRef = useRef<number>(0);
  const closeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ── Shared helper: stop any ongoing rAF loop ──────────────────────────────
  const stopProgressLoop = () => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  };

  // ── Shared helper: destroy the current preview audio element ─────────────
  const destroyPreviewAudio = () => {
    stopProgressLoop();
    if (audioPlaybackRef.current) {
      audioPlaybackRef.current.pause();
      audioPlaybackRef.current.src = "";   // release object-URL from memory
      audioPlaybackRef.current = null;
    }
  };

  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = Math.round(s % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const totalDuration = audioDuration > 0 ? audioDuration : recordingTime;

  const displayTimeText = isPlaying
    ? `${formatTime(playbackTime)} / ${formatTime(totalDuration)}`
    : formatTime(totalDuration);

  // ── startRecording ────────────────────────────────────────────────────────
  const startRecording = async () => {
    setClosingRecording(false);
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);

    // FIX BUG 4: destroy any leftover preview audio before a new recording
    destroyPreviewAudio();
    setRecordedAudioBlob(null);
    setPlaybackTime(0);
    setIsPlaying(false);
    setAudioDuration(0);
    setRecordingTime(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000 },
      });
      streamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")
        ? "audio/ogg;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 24000 });
      mediaRecorderRef.current = recorder;
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType.includes("ogg") ? "audio/ogg" : "audio/webm" });
        // FIX BUG 4: null out old audio ref BEFORE setting new blob
        // togglePlayback checks audioPlaybackRef and if null → creates fresh Audio from new blob
        audioPlaybackRef.current = null;
        setRecordedAudioBlob(blob);
        stream.getTracks().forEach(t => t.stop());
      };
      recorder.start();
      setIsRecording(true);
      recordingStartTimeRef.current = Date.now();
      recordingTimerRef.current = setInterval(() => {
        setRecordingTime(Math.floor((Date.now() - recordingStartTimeRef.current) / 1000));
      }, 200);
    } catch (err) {
      console.error("Microphone access denied:", err);
      alert("Microphone access denied");
    }
  };

  // ── stopRecording ─────────────────────────────────────────────────────────
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    }
  };

  // ── toggleRecording ───────────────────────────────────────────────────────
  const toggleRecording = async () => {
    if (isRecording) {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
        setIsRecording(false);
        if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      }
    } else {
      await startRecording();
    }
  };

  // ── cancelRecording ───────────────────────────────────────────────────────
  const cancelRecording = () => {
    setIsRecording(false);
    setRecordingTime(0);
    if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
  };

  // ── deleteRecording ───────────────────────────────────────────────────────
  // FIX BUG 4: fully destroy the audio element so the next recording starts clean
  const deleteRecording = () => {
    destroyPreviewAudio();          // ← kills old Audio + rAF
    setRecordedAudioBlob(null);
    setPlaybackTime(0);
    setIsPlaying(false);
    setAudioDuration(0);
    setRecordingTime(0);
  };

  // ── togglePlayback ────────────────────────────────────────────────────────
  // FIX BUG 2: use requestAnimationFrame so progress is smooth and exactly follows audio.currentTime
  const togglePlayback = () => {
    if (!recordedAudioBlob) return;

    // If no audio element exists yet → create one from the CURRENT blob
    if (!audioPlaybackRef.current) {
      const url = URL.createObjectURL(recordedAudioBlob);
      const audio = new Audio(url);
      audioPlaybackRef.current = audio;

      // Get real duration once metadata is available
      audio.addEventListener("loadedmetadata", () => {
        if (isFinite(audio.duration) && audio.duration > 0) {
          setAudioDuration(audio.duration);
        }
      });

      // ── rAF-based smooth progress loop ──────────────────────────────────
      const progressLoop = () => {
        const a = audioPlaybackRef.current;
        if (!a || a.paused) return;
        setPlaybackTime(a.currentTime);
        animationFrameRef.current = requestAnimationFrame(progressLoop);
      };

      audio.onplay = () => {
        setIsPlaying(true);
        stopProgressLoop();
        animationFrameRef.current = requestAnimationFrame(progressLoop);
      };

      audio.onpause = () => {
        stopProgressLoop();
        setIsPlaying(false);
      };

      audio.onended = () => {
        stopProgressLoop();
        setIsPlaying(false);
        setPlaybackTime(0);
      };
    }

    // Toggle play / pause
    if (isPlaying) {
      audioPlaybackRef.current.pause();
    } else {
      audioPlaybackRef.current.play();
    }
  };

  // ── sendVoiceMessage ──────────────────────────────────────────────────────
  // FIX BUG 4: capture blob in a local const so the closure always holds the right blob
  const sendVoiceMessage = async () => {
    if (!recordedAudioBlob || !wsRef.current) return;

    // Capture the blob reference we want to send right now
    const blobToSend = recordedAudioBlob;
    const audioUrl = URL.createObjectURL(blobToSend);

    // Try to get real duration from the preview audio element (already loaded)
    let actualDuration = audioDuration > 0 ? audioDuration : recordingTime;

    // If preview audio element hasn't loaded metadata yet, do a quick load
    if (actualDuration === 0) {
      actualDuration = await new Promise<number>((resolve) => {
        const tmp = new Audio(audioUrl);
        const onMeta = () => {
          tmp.removeEventListener("loadedmetadata", onMeta);
          resolve(isFinite(tmp.duration) ? tmp.duration : recordingTime);
        };
        tmp.addEventListener("loadedmetadata", onMeta);
        setTimeout(() => { tmp.removeEventListener("loadedmetadata", onMeta); resolve(recordingTime); }, 600);
      });
    }

    const metadata = {
      type: "message",
      messageType: "audio",
      isAudio: true,
      audio: true,
      text: false,
      userName: loggedInUser,
      sessionId,
      duration: actualDuration,
      fileFormat: "ogg",
      codec: "opus",
      timestamp: Date.now(),
    };

    wsRef.current.send(JSON.stringify(metadata));

    setTimeout(() => {
      if (wsRef.current && blobToSend) {
        wsRef.current.send(blobToSend);   // ← send captured blob, not state

        // FIX BUG 4: destroy preview audio BEFORE clearing state
        destroyPreviewAudio();
        setRecordedAudioBlob(null);
        setPlaybackTime(0);
        setIsPlaying(false);
        setAudioDuration(0);
        setRecordingTime(0);

        if (onVoiceMessageSent) onVoiceMessageSent(actualDuration, audioUrl);
      }
    }, 100);
  };

  return {
    isRecording,
    recordingTime,
    recordedAudioBlob,
    isPlaying,
    playbackTime,
    audioDuration,
    closingRecording,
    formatTime,
    totalDuration,
    displayTimeText,
    micButtonRef,
    audioPlaybackRef,
    startRecording,
    stopRecording,
    toggleRecording,
    cancelRecording,
    deleteRecording,
    togglePlayback,
    sendVoiceMessage,
  };
}

// ─── Recording Interface Component ──────────────────────────────────────────
export function RecordingInterface({
  recordingTime,
  onCancel,
  formatTime,
}: {
  recordingTime: number;
  onCancel: () => void;
  formatTime: (s: number) => string;
}) {
  return (
    <div className="recording-interface">
      <div className="recording-indicator">
        <div className="recording-pulse" />
        <span>Recording</span>
      </div>
      <div className="recording-timer">{formatTime(recordingTime)}</div>
      <div className="recording-waveform">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="waveform-bar" style={{ animationDelay: `${i * 0.1}s` }} />
        ))}
      </div>
      <div className="recording-instructions">
        <span>Continue to Preview</span>
      </div>
      <div className="recording-controls">
        <button className="recording-cancel-btn" onClick={onCancel}>
          Continue
        </button>
      </div>
    </div>
  );
}

// ─── Voice Preview Bar Component ────────────────────────────────────────────
export function VoicePreviewBar({
  isPlaying,
  playbackTime,
  totalDuration,
  displayTimeText,
  onTogglePlayback,
  onDelete,
  onSend,
  isLoading,
  wsConnectionState,
}: {
  isPlaying: boolean;
  playbackTime: number;
  totalDuration: number;
  displayTimeText: string;
  onTogglePlayback: () => void;
  onDelete: () => void;
  onSend: () => void;
  isLoading: boolean;
  wsConnectionState: string;
}) {
  return (
    <div className="voice-preview-bar">
      <button
        className="voice-play-btn"
        onClick={onTogglePlayback}
        title={isPlaying ? "Pause" : "Play"}
      >
        {isPlaying ? <IconPlayerPause size={20} /> : <IconPlayerPlay size={20} />}
      </button>
      <div className="voice-progress-container">
        <div className="voice-progress-bar">
          <div
            className="voice-progress-fill"
            style={{
              width: totalDuration > 0 ? `${(playbackTime / totalDuration) * 100}%` : "0%",
              transition: "width 0.1s linear",   // ← smooth CSS transition
            }}
          />
        </div>
      </div>
      <span className="voice-duration">{displayTimeText}</span>
      <button className="voice-delete-btn" onClick={onDelete} title="Delete">
        <IconTrash size={20} />
      </button>
      <button
        className="voice-send-btn"
        onClick={onSend}
        disabled={isLoading || wsConnectionState !== "connected"}
        title="Send voice message"
      >
        <IconSend size={20} />
      </button>
    </div>
  );
}

// ─── Mic Button Component ──────────────────────────────────────────────────
export function VoiceMicButton({
  forwardedRef,
  onClick,
  disabled,
}: {
  forwardedRef: React.MutableRefObject<HTMLButtonElement | null>;
  onClick: () => void | Promise<void>;
  disabled: boolean;
}) {
  return (
    <button
      ref={forwardedRef}
      className="voice-mic-btn"
      onClick={async () => { await onClick(); }}
      disabled={disabled}
      title="Click to record, click again to stop"
    >
      <IconMicrophone size={20} />
    </button>
  );
}