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

export interface ChatResponse {
  response: string;
  conversation_id: string;
}
