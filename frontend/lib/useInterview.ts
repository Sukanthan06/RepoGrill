"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  endSession,
  getSession,
  submitAnswer,
  transcribe,
  withRateLimitRetry,
} from "./api";
import { LiveCaptions, PushToTalkRecorder, speak, stopSpeaking } from "./audio";
import type { RepoMeta, Turn, TurnOut } from "./types";

export type VoiceState =
  | "loading"
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "rate-limited"
  | "done"
  | "error";

function describeError(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function useInterview(sessionId: string) {
  const [state, setState] = useState<VoiceState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [rateLimitWait, setRateLimitWait] = useState<number | null>(null);
  const [repo, setRepo] = useState<RepoMeta | null>(null);
  const [transcript, setTranscript] = useState<Turn[]>([]);
  const [current, setCurrent] = useState<TurnOut | null>(null);
  const [draft, setDraft] = useState("");
  const [liveCaption, setLiveCaption] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const recorderRef = useRef<PushToTalkRecorder | null>(null);
  const captionsRef = useRef<LiveCaptions | null>(null);
  const voiceEnabledRef = useRef(true);
  const stateRef = useRef<VoiceState>("loading");

  const changeState = useCallback((next: VoiceState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const onRateLimited = useCallback(
    (wait: number) => {
      setRateLimitWait(wait);
      changeState("rate-limited");
    },
    [changeState],
  );

  const say = useCallback(
    async (text: string, after: VoiceState) => {
      if (voiceEnabledRef.current) {
        changeState("speaking");
        await speak(text);
      }
      // A skip or a new recording may have changed state while we were speaking.
      if (stateRef.current === "speaking" || !voiceEnabledRef.current) changeState(after);
    },
    [changeState],
  );

  useEffect(() => {
    let cancelled = false;
    getSession(sessionId)
      .then((session) => {
        if (cancelled) return;
        setRepo(session.repo_meta);
        setTranscript(session.transcript);
        setCurrent(session.current_turn);
        if (session.done) changeState("done");
        else if (session.current_turn) void say(session.current_turn.text, "idle");
        else changeState("idle");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(describeError(err, "Could not load this interview"));
        changeState("error");
      });
    return () => {
      cancelled = true;
      stopSpeaking();
    };
  }, [sessionId, say, changeState]);

  useEffect(() => {
    return () => recorderRef.current?.dispose();
  }, []);

  const setVoice = useCallback((enabled: boolean) => {
    voiceEnabledRef.current = enabled;
    setVoiceEnabled(enabled);
    if (!enabled) stopSpeaking();
  }, []);

  const skipSpeaking = useCallback(() => {
    stopSpeaking();
    if (stateRef.current === "speaking") changeState("idle");
  }, [changeState]);

  const stopListening = useCallback(async () => {
    if (stateRef.current !== "listening") return;
    changeState("transcribing");
    const recording = await recorderRef.current?.stop();
    const captionText = (await captionsRef.current?.stop()) ?? "";
    setLiveCaption("");
    let text = captionText;
    if (recording) {
      try {
        const result = await withRateLimitRetry(
          () => transcribe(recording.blob, recording.durationSeconds),
          onRateLimited,
        );
        text = result.text || captionText;
      } catch {
        // Fall back to the browser's own captions captured during recording.
        text = captionText;
      }
    }
    if (text) {
      setDraft((previous) => (previous ? `${previous.trimEnd()} ${text}` : text));
      setError(null);
    } else {
      setError("Didn't catch that. Try again or type your answer.");
    }
    changeState("idle");
  }, [changeState, onRateLimited]);

  const startListening = useCallback(async () => {
    const now = stateRef.current;
    if (now !== "idle" && now !== "speaking") return;
    stopSpeaking();
    setError(null);
    changeState("listening");
    captionsRef.current = new LiveCaptions(setLiveCaption);
    captionsRef.current.start();
    if (!PushToTalkRecorder.isSupported()) {
      if (!LiveCaptions.isSupported()) {
        setError("This browser can't record audio. Type your answer instead.");
        changeState("idle");
      }
      return;
    }
    recorderRef.current ??= new PushToTalkRecorder();
    try {
      await recorderRef.current.start(() => void stopListening());
      // Key released while the mic was still opening: discard this recording.
      if (stateRef.current !== "listening") await recorderRef.current.stop();
    } catch {
      await captionsRef.current.stop();
      setError("Microphone unavailable. Allow mic access or type your answer.");
      changeState("idle");
    }
  }, [changeState, stopListening]);

  const submit = useCallback(async () => {
    const text = draft.trim();
    if (!text || stateRef.current !== "idle" || !current) return;
    const answerTurn: Turn = {
      speaker: "candidate",
      kind: "answer",
      text,
      question_index: current.question_number - 1,
    };
    setTranscript((turns) => [...turns, answerTurn]);
    setDraft("");
    setError(null);
    changeState("thinking");
    try {
      const response = await withRateLimitRetry(() => submitAnswer(sessionId, text), onRateLimited);
      setRateLimitWait(null);
      const next = response.next_turn;
      setTranscript((turns) => [
        ...turns,
        {
          speaker: "interviewer",
          kind: next.kind,
          text: next.text,
          question_index: next.question_number - 1,
        },
      ]);
      setCurrent(next);
      await say(next.text, response.done ? "done" : "idle");
      if (response.done) changeState("done");
    } catch (err) {
      setTranscript((turns) => turns.filter((turn) => turn !== answerTurn));
      setDraft(text);
      setRateLimitWait(null);
      setError(describeError(err, "Something went wrong sending your answer. Try again."));
      changeState("idle");
    }
  }, [draft, current, sessionId, onRateLimited, say, changeState]);

  const endEarly = useCallback(async () => {
    stopSpeaking();
    try {
      const response = await endSession(sessionId);
      setTranscript((turns) => [
        ...turns,
        {
          speaker: "interviewer",
          kind: "closing",
          text: response.next_turn.text,
          question_index: response.next_turn.question_number - 1,
        },
      ]);
      setCurrent(response.next_turn);
      changeState("done");
    } catch (err) {
      setError(describeError(err, "Could not end the interview"));
    }
  }, [sessionId, changeState]);

  const replay = useCallback(() => {
    if (current && stateRef.current === "idle") void say(current.text, "idle");
  }, [current, say]);

  const level = useCallback(() => recorderRef.current?.level() ?? 0, []);

  return {
    state,
    error,
    rateLimitWait,
    repo,
    transcript,
    current,
    draft,
    setDraft,
    liveCaption,
    voiceEnabled,
    setVoice,
    startListening,
    stopListening,
    submit,
    skipSpeaking,
    endEarly,
    replay,
    level,
  };
}

export type InterviewController = ReturnType<typeof useInterview>;
