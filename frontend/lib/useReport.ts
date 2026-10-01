"use client";

import { useEffect, useState } from "react";

import { ApiError, getReport, withRateLimitRetry } from "./api";
import type { Report } from "./types";

const STAGES = [
  "Pulling the technical claims out of your answers…",
  "Checking each claim against the code…",
  "Grading depth, accuracy and clarity…",
  "Writing your prep list…",
];
const STAGE_MS = 7000;

export function useReport(sessionId: string) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState(0);
  const [rateLimitWait, setRateLimitWait] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), STAGE_MS);
    withRateLimitRetry(
      () => getReport(sessionId),
      (wait) => !cancelled && setRateLimitWait(wait),
      4,
    )
      .then((result) => !cancelled && setReport(result))
      .catch(
        (err: unknown) =>
          !cancelled &&
          setError(err instanceof ApiError ? err.message : "Could not build the scorecard"),
      )
      .finally(() => clearInterval(timer));
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [sessionId]);

  return { report, error, stageText: STAGES[stage], rateLimitWait };
}
