"use client";

import { useRef, useEffect, useCallback, type MutableRefObject, type RefObject } from "react";
import {
  buildGhostCandidates,
  ghostPromptHistoryStorageKey,
  pickInlineGhostSuffix,
  type GhostCompletionMessage,
} from "../lib/ghostInputCompletion";

export type WsConnectionState = "connecting" | "connected" | "failed";

export function useGhostInputCompletion(
  messages: GhostCompletionMessage[],
  loggedInUser: string | null,
  rawInputRef: MutableRefObject<string>,
  inputRef: RefObject<HTMLTextAreaElement | null>,
  isLoading: boolean,
  wsConnectionState: WsConnectionState,
) {
  const ghostUserSpanRef = useRef<HTMLSpanElement | null>(null);
  const ghostSuffixSpanRef = useRef<HTMLSpanElement | null>(null);
  const ghostSuffixStrRef = useRef("");
  const isComposingRef = useRef(false);
  const ghostCandidatesRef = useRef<string[]>([]);

  const clearGhostCompletion = useCallback(() => {
    ghostSuffixStrRef.current = "";
    if (ghostSuffixSpanRef.current) ghostSuffixSpanRef.current.textContent = "";
  }, []);

  const syncGhostUserMirror = useCallback(() => {
    const ta = inputRef.current;
    const span = ghostUserSpanRef.current;
    if (ta && span) span.textContent = ta.value;
  }, [inputRef]);

  const applyGhostSuffixFromInput = useCallback(() => {
    if (isComposingRef.current) return;
    const ta = inputRef.current;
    if (ta) {
      if (ta.scrollTop > 0 || ta.scrollHeight > ta.clientHeight + 2) {
        clearGhostCompletion();
        return;
      }
    }
    const val = rawInputRef.current;
    const suffix = pickInlineGhostSuffix(val, ghostCandidatesRef.current);
    ghostSuffixStrRef.current = suffix;
    if (ghostSuffixSpanRef.current) ghostSuffixSpanRef.current.textContent = suffix;
  }, [inputRef, rawInputRef, clearGhostCompletion]);

  useEffect(() => {
    const key = ghostPromptHistoryStorageKey(loggedInUser);
    ghostCandidatesRef.current = buildGhostCandidates(messages, key);
    applyGhostSuffixFromInput();
  }, [messages, loggedInUser, applyGhostSuffixFromInput]);

  useEffect(() => {
    const inputDisabled = isLoading || wsConnectionState !== "connected";
    if (inputDisabled) clearGhostCompletion();
  }, [isLoading, wsConnectionState, clearGhostCompletion]);

  return {
    ghostUserSpanRef,
    ghostSuffixSpanRef,
    ghostSuffixStrRef,
    isComposingRef,
    clearGhostCompletion,
    syncGhostUserMirror,
    applyGhostSuffixFromInput,
  };
}
