"use client";

import { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getInvestigation,
  getLatestDisputeInvestigation,
  investigationStreamEndpoint,
  resumeInvestigation,
  startInvestigation,
} from "@/lib/api";
import {
  applyRunToConsoleState,
  applyStreamEventToConsoleState,
  computeIterationDiff,
  deriveConsoleStateAtStep,
  extractIterationSnapshots,
  initialConsoleState,
  mergeUniqueEvents,
} from "@/lib/investigationState";
import { shouldReconnectInvestigation, streamReconnectDelayMs } from "@/lib/investigationStream";
import { openInvestigationStream } from "@/lib/sse";
import { ApprovalDecision, ConsoleState, InvestigationRun, StreamEvent } from "@/lib/types";

type StreamHandle = {
  close: () => void;
};

export const useSentinelAgent = (disputeId: string) => {
  const [state, setState] = useState<ConsoleState>(initialConsoleState);
  const [rawEvents, setRawEvents] = useState<StreamEvent[]>([]);
  const [baseRun, setBaseRun] = useState<InvestigationRun | null>(null);
  const [selectedEventIndex, setSelectedEventIndex] = useState<number | null>(null);
  const [isHydrated, setIsHydrated] = useState<boolean>(false);

  const [isLaunching, setIsLaunching] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const stateRef = useRef(state);
  stateRef.current = state;
  const isLaunchingRef = useRef(isLaunching);
  isLaunchingRef.current = isLaunching;
  const isReviewingRef = useRef(isReviewing);
  isReviewingRef.current = isReviewing;
  const streamRef = useRef<StreamHandle | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const clearReconnectTimeout = () => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  };

  const resetReconnectState = () => {
    reconnectAttemptRef.current = 0;
    clearReconnectTimeout();
  };

  const refresh = useCallback(async (investigationId: string, reconnectIfRunning = false) => {
    try {
      const run = await getInvestigation(investigationId);
      setBaseRun(run);
      const hydratedEvents = Array.isArray(run.timeline_events)
        ? (run.timeline_events as unknown as StreamEvent[])
        : [];
      if (hydratedEvents.length > 0) {
        setRawEvents((prev) => mergeUniqueEvents(prev, hydratedEvents));
      }
      setState((current) => applyRunToConsoleState(current, run));
      if (reconnectIfRunning && shouldReconnectInvestigation(run, reconnectAttemptRef.current)) {
        connectStream(run.id, false);
      }
    } catch (error) {
      setState((current) => ({
        ...current,
        streamConnection: "disconnected",
        nextReconnectDelayMs: null,
        error: error instanceof Error ? error.message : "Refresh failed.",
      }));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    clearReconnectTimeout();
    streamRef.current?.close();
    streamRef.current = null;
    resetReconnectState();
    setRawEvents([]);
    setBaseRun(null);
    setSelectedEventIndex(null);
    setIsHydrated(false);
    setState(initialConsoleState);

    const hydrateDisputeInvestigation = async () => {
      try {
        const latestRun = await getLatestDisputeInvestigation(disputeId);
        if (cancelled || !latestRun) {
          return;
        }
        setBaseRun(latestRun);
        const hydratedEvents = Array.isArray(latestRun.timeline_events)
          ? (latestRun.timeline_events as unknown as StreamEvent[])
          : [];
        if (hydratedEvents.length > 0) {
          setRawEvents((prev) => mergeUniqueEvents(prev, hydratedEvents));
        }
        setState((current) => applyRunToConsoleState(current, latestRun));
        if (latestRun.status === "running" || latestRun.status === "pending") {
          connectStream(latestRun.id);
        }
      } catch {
        // Dispute may not have an investigation yet; remain in IDLE state cleanly.
      } finally {
        if (!cancelled) {
          setIsHydrated(true);
        }
      }
    };

    void hydrateDisputeInvestigation();

    return () => {
      cancelled = true;
      clearReconnectTimeout();
      streamRef.current?.close();
      streamRef.current = null;
    };
  }, [disputeId]);

  const scheduleReconnect = (investigationId: string, message: string) => {
    streamRef.current = null;
    clearReconnectTimeout();
    const delayMs = streamReconnectDelayMs(reconnectAttemptRef.current);
    reconnectAttemptRef.current += 1;
    setState((current) => ({
      ...current,
      isStreaming: false,
      streamConnection: "reconnecting",
      reconnectAttempt: reconnectAttemptRef.current,
      nextReconnectDelayMs: delayMs,
      error: message,
    }));
    reconnectTimeoutRef.current = window.setTimeout(() => {
      reconnectTimeoutRef.current = null;
      void refresh(investigationId, true);
    }, delayMs);
  };

  const connectStream = (investigationId: string, resetRetries = true) => {
    streamRef.current?.close();
    clearReconnectTimeout();
    if (resetRetries) {
      reconnectAttemptRef.current = 0;
    }
    setState((current) => ({
      ...current,
      isStreaming: true,
      streamConnection: reconnectAttemptRef.current > 0 ? "reconnecting" : "connected",
      reconnectAttempt: reconnectAttemptRef.current,
      nextReconnectDelayMs: null,
      error: null,
    }));
    streamRef.current = openInvestigationStream(
      investigationStreamEndpoint(investigationId),
      (event) => {
        resetReconnectState();
        if (
          event.type === "approval_required" ||
          event.type === "run_completed" ||
          event.type === "run_failed"
        ) {
          streamRef.current?.close();
          streamRef.current = null;
        }
        startTransition(() => {
          if (event.type !== "reasoning_delta" && event.type !== "synthesis_delta") {
            setRawEvents((prev) => mergeUniqueEvents(prev, [event]));
          }
          setState((current) =>
            applyStreamEventToConsoleState(
              {
                ...current,
                reconnectAttempt: 0,
                nextReconnectDelayMs: null,
              },
              event
            )
          );
        });
      },
      (message) => {
        if (reconnectAttemptRef.current >= 3) {
          setState((current) => ({
            ...current,
            isStreaming: false,
            streamConnection: "disconnected",
            nextReconnectDelayMs: null,
            error: message,
          }));
          void refresh(investigationId, false);
          return;
        }
        scheduleReconnect(investigationId, message);
      },
      () => {
        if (reconnectAttemptRef.current >= 3) {
          setState((current) => ({
            ...current,
            isStreaming: false,
            streamConnection: "disconnected",
            nextReconnectDelayMs: null,
            error: current.status === "RUNNING" ? "Stream connection closed." : current.error,
          }));
          void refresh(investigationId, false);
          return;
        }
        scheduleReconnect(investigationId, "Stream connection closed.");
      }
    );
  };

  const launch = useCallback(async () => {
    if (isLaunchingRef.current) {
      return;
    }
    setIsLaunching(true);
    setRawEvents([]);
    setSelectedEventIndex(null);
    setState((current) => ({
      ...current,
      status: "RUNNING",
      streamConnection: "disconnected",
      error: null,
    }));
    try {
      const run = await startInvestigation(disputeId);
      setBaseRun(run);
      setState((current) => applyRunToConsoleState(current, run));
      connectStream(run.id);
    } catch (error) {
      setState((current) => ({
        ...current,
        status: "FAILED",
        streamConnection: "idle",
        error: error instanceof Error ? error.message : "Investigation failed.",
      }));
    } finally {
      setIsLaunching(false);
    }
  }, [disputeId]);

  const review = useCallback(
    async (decision: ApprovalDecision, comment: string, guidance?: string) => {
      const investigationId = stateRef.current.investigationId;
      if (!investigationId || isReviewingRef.current) {
        return;
      }
      setIsReviewing(true);
      try {
        const run = await resumeInvestigation(investigationId, decision, comment, guidance);
        setBaseRun(run);
        setState((current) => applyRunToConsoleState(current, run));
        connectStream(run.id);
      } catch (error) {
        setState((current) => ({
          ...current,
          streamConnection: "disconnected",
          nextReconnectDelayMs: null,
          error: error instanceof Error ? error.message : "Approval failed.",
        }));
      } finally {
        setIsReviewing(false);
      }
    },
    []
  );

  // Time-travel derived console state
  const displayState = useMemo(() => {
    if (selectedEventIndex === null || rawEvents.length === 0) {
      return state;
    }
    return deriveConsoleStateAtStep(rawEvents, baseRun, selectedEventIndex);
  }, [selectedEventIndex, rawEvents, baseRun, state]);

  const goToStep = useCallback(
    (index: number | null) => {
      if (index === null) {
        setSelectedEventIndex(null);
      } else {
        setSelectedEventIndex(Math.min(Math.max(0, index), Math.max(0, rawEvents.length - 1)));
      }
    },
    [rawEvents.length]
  );

  const goToPreviousStep = useCallback(() => {
    if (rawEvents.length === 0) {
      return;
    }
    setSelectedEventIndex((prev) => {
      if (prev === null) {
        return Math.max(0, rawEvents.length - 2);
      }
      return Math.max(0, prev - 1);
    });
  }, [rawEvents.length]);

  const goToNextStep = useCallback(() => {
    if (rawEvents.length === 0) {
      return;
    }
    setSelectedEventIndex((prev) => {
      if (prev === null) {
        return null;
      }
      if (prev >= rawEvents.length - 2) {
        return null; // Snap back to live head on reaching latest
      }
      return prev + 1;
    });
  }, [rawEvents.length]);

  const goToLiveHead = useCallback(() => {
    setSelectedEventIndex(null);
  }, []);

  const iterationSnapshots = useMemo(() => {
    return extractIterationSnapshots(rawEvents);
  }, [rawEvents]);

  const iterationDiffs = useMemo(() => {
    if (iterationSnapshots.length < 2) {
      return [];
    }
    const diffs = [];
    for (let i = 1; i < iterationSnapshots.length; i += 1) {
      diffs.push(computeIterationDiff(iterationSnapshots[i - 1], iterationSnapshots[i]));
    }
    return diffs;
  }, [iterationSnapshots]);

  return {
    state: displayState,
    liveState: state,
    rawEvents,
    selectedEventIndex,
    isHydrated,
    setSelectedEventIndex,
    isLive: selectedEventIndex === null,
    goToStep,
    goToPreviousStep,
    goToNextStep,
    goToLiveHead,
    iterationSnapshots,
    iterationDiffs,
    isLaunching,
    isReviewing,
    launch,
    refresh,
    review,
  };
};
