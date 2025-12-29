import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useChatStore } from "../stores/chatStore";
import { createLogger } from "@/lib/logger";
import type { MemoryContext } from "@/types";

export function useChat() {
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const abortControllerRef = useRef<AbortController | null>(null);

	// Create logger with conversation context
	const logger = useMemo(() => createLogger("useChat"), []);

	const {
		addMessage,
		updateMessage,
		setStreaming,
		setStreamingContent,
		appendStreamingContent,
		setMemoryContext,
	} = useChatStore();

	// Cleanup on unmount
	useEffect(() => {
		logger.debug("hook_mounted");
		return () => {
			logger.debug("hook_unmounted");
			abortControllerRef.current?.abort();
		};
	}, [logger]);

	const cancelRequest = useCallback(() => {
		if (abortControllerRef.current) {
			logger.info("request_cancelled");
			abortControllerRef.current.abort();
			abortControllerRef.current = null;
			setIsLoading(false);
			setStreaming(false);
		}
	}, [logger, setStreaming]);

	const sendMessage = useCallback(
		async (content: string) => {
			// Abort any existing request
			if (abortControllerRef.current) {
				logger.debug("aborting_previous_request");
				abortControllerRef.current.abort();
			}
			abortControllerRef.current = new AbortController();

			const startTime = performance.now();
			logger.info("message_send_started", { message_length: content.length });

			setIsLoading(true);
			setError(null);

			// Add user message
			addMessage({ role: "user", content });

			// Add placeholder for assistant message
			const assistantId = addMessage({ role: "assistant", content: "" });

			try {
				setStreaming(true);
				setStreamingContent("");
				setMemoryContext(null); // Clear previous context

				const response = await fetch("/api/v1/chat/stream", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ message: content }),
					signal: abortControllerRef.current.signal,
				});

				if (!response.ok) {
					throw new Error(`HTTP ${response.status}`);
				}

				const reader = response.body?.getReader();
				const decoder = new TextDecoder();

				if (!reader) {
					throw new Error("No response body");
				}

				let fullContent = "";
				let currentEvent = "";
				let tokenCount = 0;

				while (true) {
					const { done, value } = await reader.read();
					if (done) break;

					const chunk = decoder.decode(value);
					const lines = chunk.split("\n");

					for (const line of lines) {
						// Track current event type
						if (line.startsWith("event: ")) {
							currentEvent = line.slice(7).trim();
							continue;
						}

						// Handle data based on event type
						if (line.startsWith("data: ")) {
							const data = line.slice(6);
							if (data === "[DONE]") continue;

							try {
								const parsed = JSON.parse(data);

								// Handle context event before tokens
								if (currentEvent === "context" && parsed.memory_context) {
									const memoryContext = parsed.memory_context as MemoryContext;
									logger.debug("memory_context_received", {
										memory_count: memoryContext.memories?.length ?? 0,
									});
									setMemoryContext(memoryContext, assistantId);
								}
								// Handle token event
								else if (currentEvent === "token" && parsed.chunk) {
									fullContent += parsed.chunk;
									tokenCount++;
									appendStreamingContent(parsed.chunk);
									updateMessage(assistantId, fullContent);
								}
								// Fallback for data without explicit event type
								else if (parsed.chunk) {
									fullContent += parsed.chunk;
									tokenCount++;
									appendStreamingContent(parsed.chunk);
									updateMessage(assistantId, fullContent);
								}
							} catch {
								// Not JSON, might be plain text token
								if (currentEvent === "token" || currentEvent === "") {
									fullContent += data;
									tokenCount++;
									appendStreamingContent(data);
									updateMessage(assistantId, fullContent);
								}
							}
						}
					}
				}

				const duration = Math.round(performance.now() - startTime);
				logger.info("message_send_completed", {
					duration_ms: duration,
					response_length: fullContent.length,
					token_count: tokenCount,
				});
			} catch (err) {
				// Don't show error for intentional aborts
				if (err instanceof DOMException && err.name === "AbortError") {
					logger.debug("request_aborted");
					return;
				}
				const message = err instanceof Error ? err.message : "Unknown error";
				const duration = Math.round(performance.now() - startTime);
				logger.error("message_send_failed", {
					error: err instanceof Error ? err : new Error(message),
					duration_ms: duration,
				});
				setError(message);
				updateMessage(assistantId, `Error: ${message}`);
			} finally {
				setStreaming(false);
				setIsLoading(false);
			}
		},
		[
			logger,
			addMessage,
			updateMessage,
			setStreaming,
			setStreamingContent,
			appendStreamingContent,
			setMemoryContext,
		],
	);

	return {
		sendMessage,
		cancelRequest,
		isLoading,
		error,
	};
}
