import { useState, useCallback } from "react";
import { useChatStore } from "../stores/chatStore";
import type { MemoryContext } from "@/types";

export function useChat() {
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const {
		addMessage,
		updateMessage,
		setStreaming,
		setStreamingContent,
		appendStreamingContent,
		setMemoryContext,
	} = useChatStore();

	const sendMessage = useCallback(
		async (content: string) => {
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
									setMemoryContext(
										parsed.memory_context as MemoryContext,
										assistantId,
									);
								}
								// Handle token event
								else if (currentEvent === "token" && parsed.chunk) {
									fullContent += parsed.chunk;
									appendStreamingContent(parsed.chunk);
									updateMessage(assistantId, fullContent);
								}
								// Fallback for data without explicit event type
								else if (parsed.chunk) {
									fullContent += parsed.chunk;
									appendStreamingContent(parsed.chunk);
									updateMessage(assistantId, fullContent);
								}
							} catch {
								// Not JSON, might be plain text token
								if (currentEvent === "token" || currentEvent === "") {
									fullContent += data;
									appendStreamingContent(data);
									updateMessage(assistantId, fullContent);
								}
							}
						}
					}
				}
			} catch (err) {
				const message = err instanceof Error ? err.message : "Unknown error";
				setError(message);
				updateMessage(assistantId, `Error: ${message}`);
			} finally {
				setStreaming(false);
				setIsLoading(false);
			}
		},
		[
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
		isLoading,
		error,
	};
}
