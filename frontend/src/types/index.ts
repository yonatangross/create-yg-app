/**
 * Shared TypeScript types
 */

export interface ApiError {
	error: {
		code: string;
		message: string;
		request_id?: string;
	};
}

export interface ChatRequest {
	message: string;
	conversation_id?: string;
}

export interface MemoryItem {
	type: string;
	content: string;
}

export interface MemoryContext {
	memories: MemoryItem[];
	count: number;
}

export interface ChatResponse {
	response: string;
	conversation_id: string;
	memory_context?: MemoryContext;
}
