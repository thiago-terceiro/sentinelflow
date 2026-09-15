"use client";

import { startTransition, useEffect, useRef, useState } from "react";

import {
    getInvestigation,
    investigationStreamEndpoint,
    resumeInvestigation,
    startInvestigation,
} from "@/lib/api";
import {
    applyRunToConsoleState,
    applyStreamEventToConsoleState,
    initialConsoleState,
} from "@/lib/investigationState";
import { shouldReconnectInvestigation, streamReconnectDelayMs } from "@/lib/investigationStream";
import { openInvestigationStream } from "@/lib/sse";
import { ConsoleState } from "@/lib/types";

type StreamHandle = {
    close: () => void;
};

export const useSentinelAgent = (disputeId: string) => {
    const [state, setState] = useState<ConsoleState>(initialConsoleState);
    const [isLaunching, setIsLaunching] = useState(false);
    const [isReviewing, setIsReviewing] = useState(false);
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

    useEffect(() => {
        return () => {
            clearReconnectTimeout();
            streamRef.current?.close();
        };
    }, []);

    const refresh = async (investigationId: string, reconnectIfRunning = false) => {
        try {
            const run = await getInvestigation(investigationId);
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
    };

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
                    setState((current) => applyStreamEventToConsoleState({
                        ...current,
                        reconnectAttempt: 0,
                        nextReconnectDelayMs: null,
                    }, event));
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
            },
        );
    };

    const launch = async () => {
        if (isLaunching) {
            return;
        }
        setIsLaunching(true);
        setState((current) => ({
            ...current,
            status: "RUNNING",
            streamConnection: "disconnected",
            error: null,
        }));
        try {
            const run = await startInvestigation(disputeId);
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
    };

    const review = async (decision: "approve" | "deny", comment: string) => {
        if (!state.investigationId || isReviewing) {
            return;
        }
        setIsReviewing(true);
        try {
            const run = await resumeInvestigation(state.investigationId, decision, comment);
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
    };

    return {
        state,
        isLaunching,
        isReviewing,
        launch,
        refresh,
        review,
    };
};
