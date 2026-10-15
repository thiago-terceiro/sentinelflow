import type { StreamEvent } from "./types";

type InvestigationStream = {
    close: () => void;
};

const parseEventChunk = (chunk: string): StreamEvent[] => {
    return chunk
        .split("\n\n")
        .map((eventBlock) => {
            const dataLines = eventBlock
                .split("\n")
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trimStart());
            if (dataLines.length === 0) {
                return null;
            }
            try {
                return JSON.parse(dataLines.join("\n")) as StreamEvent;
            } catch {
                throw new Error("Malformed SSE payload.");
            }
        })
        .filter((event): event is StreamEvent => event !== null);
};

export const openInvestigationStream = (
    url: string,
    onEvent: (event: StreamEvent) => void,
    onError: (message: string) => void,
    onClose?: () => void,
): InvestigationStream => {
    const controller = new AbortController();
    const decoder = new TextDecoder();
    let closedByCaller = false;

    const consume = async () => {
        try {
            const response = await fetch(url, {
                headers: {
                    Accept: "text/event-stream",
                },
                cache: "no-store",
                signal: controller.signal,
            });

            if (!response.ok) {
                onError(`Stream request failed with status ${response.status}.`);
                return;
            }

            if (!response.body) {
                onError("Stream response body is missing.");
                return;
            }

            const reader = response.body.getReader();
            let buffer = "";

            while (!controller.signal.aborted) {
                const { done, value } = await reader.read();
                if (done) {
                    break;
                }
                buffer += decoder.decode(value, { stream: true });
                const completeLength = buffer.lastIndexOf("\n\n");
                if (completeLength === -1) {
                    continue;
                }
                const completeChunk = buffer.slice(0, completeLength);
                buffer = buffer.slice(completeLength + 2);
                for (const event of parseEventChunk(completeChunk)) {
                    onEvent(event);
                }
            }

            const trailing = buffer + decoder.decode();
            if (trailing.trim().length > 0) {
                for (const event of parseEventChunk(trailing)) {
                    onEvent(event);
                }
            }
            if (closedByCaller || controller.signal.aborted) {
                return;
            }
            onClose?.();
        } catch (error) {
            if (controller.signal.aborted) {
                return;
            }
            onError(error instanceof Error ? error.message : "Stream connection failed.");
        }
    };

    void consume();

    return {
        close: () => {
            closedByCaller = true;
            controller.abort();
        },
    };
};
