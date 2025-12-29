/**
 * Shared TypeScript types with Zod runtime validation
 */

import { z } from "zod";
import { createLogger } from "@/lib/logger";

const logger = createLogger("Validation");

// --- Zod Schemas for Runtime Validation ---

export const ApiErrorSchema = z.object({
	error: z.object({
		code: z.string(),
		message: z.string(),
		request_id: z.string().optional(),
	}),
});

export const ChatRequestSchema = z.object({
	message: z.string().min(1, "Message cannot be empty"),
	conversation_id: z.string().uuid().optional(),
});

export const MemoryItemSchema = z.object({
	type: z.string().min(1),
	content: z.string(),
});

export const MemoryContextSchema = z.object({
	memories: z.array(MemoryItemSchema),
	count: z.number().int().nonnegative(),
});

export const ChatResponseSchema = z.object({
	response: z.string(),
	conversation_id: z.string(),
	memory_context: MemoryContextSchema.optional(),
});

// --- Inferred TypeScript Types ---

export type ApiError = z.infer<typeof ApiErrorSchema>;
export type ChatRequest = z.infer<typeof ChatRequestSchema>;
export type MemoryItem = z.infer<typeof MemoryItemSchema>;
export type MemoryContext = z.infer<typeof MemoryContextSchema>;
export type ChatResponse = z.infer<typeof ChatResponseSchema>;

// --- Validation Helpers ---

/**
 * Safely parse memory context from API response.
 * Returns null if validation fails.
 */
export function parseMemoryContext(data: unknown): MemoryContext | null {
	const result = MemoryContextSchema.safeParse(data);
	if (result.success) {
		return result.data;
	}
	logger.warn("memory_context_validation_failed", {
		schema: "MemoryContext",
		issues: result.error.issues.map((issue) => ({
			path: issue.path.join("."),
			message: issue.message,
		})),
	});
	return null;
}

/**
 * Safely parse chat response from API.
 * Returns null if validation fails.
 */
export function parseChatResponse(data: unknown): ChatResponse | null {
	const result = ChatResponseSchema.safeParse(data);
	if (result.success) {
		return result.data;
	}
	logger.warn("chat_response_validation_failed", {
		schema: "ChatResponse",
		issues: result.error.issues.map((issue) => ({
			path: issue.path.join("."),
			message: issue.message,
		})),
	});
	return null;
}
