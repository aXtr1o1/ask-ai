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
  // ─── Recording State ─────────────────────────────────────────────────
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordedAudioBlob, setRecordedAudioBlob] = useState<Blob | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [closingRecording, setClosingRecording] = useState(false);

  // ─── Refs ─────────────────────────────────────────────────────────────
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const micButtonRef = useRef<HTMLButtonElement>(null);
  const audioPlaybackRef = useRef<HTMLAudioElement | null>(null);
  const recordingStartTimeRef = useRef<number>(0);
  const closeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ─── FIX 1: Track recordingTime in a ref so sendVoiceMessage always
  //     reads the value AT send time, not after state resets ─────────────
  const recordingTimeRef = useRef<number>(0);
  useEffect(() => {
    recordingTimeRef.current = recordingTime;
  }, [recordingTime]);

  // ─── Shared clean formatter: Math.floor prevents float bleed ──────────
  //     e.g. 6.720001 → "0:06" never "0:6.720001"
  const fmt = (s: number) =>
    `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

  return {
    isRecording,
    recordingTime,
    recordedAudioBlob,
    isPlaying,
    playbackTime,
    audioDuration,
    closingRecording,

    // ─── FIX 2: Use fmt() — Math.floor on secs, never Math.round ─────────
    formatTime: (s: number) => fmt(s),

    totalDuration: audioDuration > 0 ? audioDuration : recordingTime,

    // ─── FIX 3: fmt() used everywhere — clean integers only ───────────────
    displayTimeText: (() => {
      const dur = audioDuration > 0 ? audioDuration : recordingTime;
      return isPlaying ? `${fmt(playbackTime)} / ${fmt(dur)}` : fmt(dur);
    })(),

    micButtonRef,
    audioPlaybackRef,

    // ─── startRecording ───────────────────────────────────────────────────
    startRecording: async () => {
      setClosingRecording(false);
      if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
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
          setRecordedAudioBlob(blob);
          stream.getTracks().forEach(t => t.stop());
        };
        recorder.start();
        setIsRecording(true);
        recordingStartTimeRef.current = Date.now();
        recordingTimerRef.current = setInterval(() => {
          setRecordingTime(Math.floor((Date.now() - recordingStartTimeRef.current) / 1000));
        }, 100);
      } catch (err) {
        console.error("Microphone access denied:", err);
        alert("Microphone access denied");
      }
    },

    // ─── stopRecording ────────────────────────────────────────────────────
    stopRecording: () => {
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
        setIsRecording(false);
        if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      }
    },

    // ─── toggleRecording ──────────────────────────────────────────────────
    toggleRecording: async () => {
      if (isRecording) {
        if (mediaRecorderRef.current) {
          mediaRecorderRef.current.stop();
          setIsRecording(false);
          if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
        }
      } else {
        setClosingRecording(false);
        if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
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
            setRecordedAudioBlob(blob);
            stream.getTracks().forEach(t => t.stop());
          };
          recorder.start();
          setIsRecording(true);
          recordingStartTimeRef.current = Date.now();
          recordingTimerRef.current = setInterval(() => {
            setRecordingTime(Math.floor((Date.now() - recordingStartTimeRef.current) / 1000));
          }, 100);
        } catch (err) {
          console.error("Microphone access denied:", err);
          alert("Microphone access denied");
        }
      }
    },

    // ─── cancelRecording ──────────────────────────────────────────────────
    cancelRecording: () => {
      setIsRecording(false);
      setRecordingTime(0);
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
      if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    },

    // ─── FIX 4: deleteRecording ───────────────────────────────────────────
    // OLD: audioPlaybackRef was paused but NOT nulled → stale Audio object
    //      (old blob URL) silently reused on next re-record.
    // FIX: null the ref fully so togglePlayback() creates fresh Audio.
    //      setRecordingTime(0) resets timer display to 0:00 after delete.
    deleteRecording: () => {
      setRecordedAudioBlob(null);
      setPlaybackTime(0);
      setIsPlaying(false);
      setAudioDuration(0);
      setRecordingTime(0);              // ← reset timer display to 0:00
      if (audioPlaybackRef.current) {
        audioPlaybackRef.current.pause();
        audioPlaybackRef.current.src = "";   // ← free old blob URL from memory
        audioPlaybackRef.current = null;     // ← destroy ref → fresh Audio on next use
      }
    },

    // ─── togglePlayback ───────────────────────────────────────────────────
    togglePlayback: () => {
      if (!recordedAudioBlob) return;
      if (!audioPlaybackRef.current) {
        const url = URL.createObjectURL(recordedAudioBlob);
        audioPlaybackRef.current = new Audio(url);
        let frameId: number | null = null;

        // ─── FIX 5: Math.floor on audio.duration → no float bleed ────────
        audioPlaybackRef.current.addEventListener("loadedmetadata", () => {
          setAudioDuration(Math.floor(audioPlaybackRef.current!.duration));
        });

        const update = () => {
          const audio = audioPlaybackRef.current;
          if (audio && !audio.paused) {
            setPlaybackTime(audio.currentTime);
            frameId = requestAnimationFrame(update);
          }
        };
        audioPlaybackRef.current.onplay = () => {
          setIsPlaying(true);
          if (frameId) cancelAnimationFrame(frameId);
          frameId = requestAnimationFrame(update);
        };
        audioPlaybackRef.current.onpause = () => {
          if (frameId) cancelAnimationFrame(frameId);
        };
        audioPlaybackRef.current.onended = () => {
          if (frameId) cancelAnimationFrame(frameId);
          setIsPlaying(false);
          setPlaybackTime(0);
        };
      }
      if (isPlaying) {
        audioPlaybackRef.current.pause();
        setIsPlaying(false);
      } else {
        audioPlaybackRef.current.play();
        setIsPlaying(true);
      }
    },

    // ─── FIX 6: sendVoiceMessage ──────────────────────────────────────────
    // OLD: used live `recordingTime` state as fallback duration.
    //      deleteRecording() sets recordingTime=0 BEFORE this runs →
    //      if loadedmetadata doesn't fire in 500ms, actualDuration = 0
    //      → onVoiceMessageSent(0) → chat bubble shows "0:00".
    // FIX: capture duration from recordingTimeRef (always current value)
    //      BEFORE any async operations or state resets can corrupt it.
    //      Also Math.floor on audio.duration to prevent float display.
    sendVoiceMessage: async () => {
      if (!recordedAudioBlob || !wsRef.current) return;

      // ─── Capture before any resets ────────────────────────────────────
      const capturedDuration = recordingTimeRef.current;

      const audioUrl = URL.createObjectURL(recordedAudioBlob);
      const audio = new Audio(audioUrl);
      let actualDuration = capturedDuration; // safe fallback — not live state

      await new Promise<void>((resolve) => {
        const onMeta = () => {
          actualDuration = Math.floor(audio.duration); // ← floor float duration
          audio.removeEventListener("loadedmetadata", onMeta);
          resolve();
        };
        audio.addEventListener("loadedmetadata", onMeta);
        setTimeout(() => {
          audio.removeEventListener("loadedmetadata", onMeta);
          resolve();
        }, 500);
      });

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
        if (wsRef.current) {
          wsRef.current.send(recordedAudioBlob);
          setRecordedAudioBlob(null);
          setPlaybackTime(0);
          setIsPlaying(false);
          if (onVoiceMessageSent) onVoiceMessageSent(actualDuration, audioUrl);
        }
      }, 100);
    },
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
  const handleClick = async () => {
    await onClick();
  };

  return (
    <button
      ref={forwardedRef}
      className="voice-mic-btn"
      onClick={handleClick}
      disabled={disabled}
      title="Click to record, click again to stop"
    >
      <IconMicrophone size={20} />
    </button>
  );
}