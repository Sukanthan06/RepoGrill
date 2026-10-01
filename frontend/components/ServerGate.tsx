"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

const SLOW_AFTER_MS = 1500;
const RETRY_MS = 3000;
const GIVE_UP_MS = 120_000;

type GateState = "checking" | "waking" | "ready" | "down";

/**
 * Free hosting sleeps idle servers. Ping the health check first and, if it is slow,
 * show a friendly "waking up" screen instead of failing requests.
 */
export function ServerGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<GateState>("checking");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();
    const slowTimer = setTimeout(() => !cancelled && setState("waking"), SLOW_AFTER_MS);

    async function poll(): Promise<void> {
      while (!cancelled) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10_000);
        try {
          await getHealth(controller.signal);
          if (!cancelled) setState("ready");
          return;
        } catch {
          if (Date.now() - started > GIVE_UP_MS) {
            if (!cancelled) setState("down");
            return;
          }
          await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
        } finally {
          clearTimeout(timeout);
        }
      }
    }
    void poll().finally(() => clearTimeout(slowTimer));
    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, [attempt]);

  if (state === "ready") return <>{children}</>;
  if (state === "checking") return null;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      {state === "waking" ? (
        <>
          <div
            className="h-14 w-14 animate-orb-pulse rounded-full bg-gradient-to-br from-orange-300 to-orange-700 shadow-lg shadow-orange-500/30"
            aria-hidden
          />
          <h1 className="text-xl font-semibold" role="status">
            Waking the server…
          </h1>
          <p className="max-w-sm text-sm text-zinc-400">
            RepoGrill runs on a free tier that naps when idle. This can take up to a minute.
          </p>
        </>
      ) : (
        <>
          <h1 className="text-xl font-semibold">Can&apos;t reach the server</h1>
          <p className="max-w-sm text-sm text-zinc-400">
            The backend didn&apos;t respond. Check your connection or try again shortly.
          </p>
          <button
            type="button"
            onClick={() => {
              setState("waking");
              setAttempt((n) => n + 1);
            }}
            className="rounded-lg bg-orange-500 px-4 py-2 font-semibold text-zinc-950 hover:bg-orange-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300"
          >
            Try again
          </button>
        </>
      )}
    </main>
  );
}
