import { create } from "zustand";
import type { MemoryContext } from "@/types";

export interface Message {
	id: string;
	role: "user" | "assistant";
	content: string;
	createdAt: Date;
}

interface ChatState {
	messages: Message[];
	isStreaming: boolean;
	streamingContent: string;
	memoryContext: MemoryContext | null;
	lastMessageMemoryContext: string | null;
	addMessage: (message: Omit<Message, "id" | "createdAt">) => string;
	updateMessage: (id: string, content: string) => void;
	setStreaming: (streaming: boolean) => void;
	setStreamingContent: (content: string) => void;
	appendStreamingContent: (chunk: string) => void;
	setMemoryContext: (context: MemoryContext | null, messageId?: string) => void;
	clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
	messages: [],
	isStreaming: false,
	streamingContent: "",
	memoryContext: null,
	lastMessageMemoryContext: null,

	addMessage: (message) => {
		const id = crypto.randomUUID();
		set((state) => ({
			messages: [
				...state.messages,
				{
					...message,
					id,
					createdAt: new Date(),
				},
			],
		}));
		return id;
	},

	updateMessage: (id, content) => {
		set((state) => ({
			messages: state.messages.map((msg) =>
				msg.id === id ? { ...msg, content } : msg,
			),
		}));
	},

	setStreaming: (streaming) => {
		set({ isStreaming: streaming });
	},

	setStreamingContent: (content) => {
		set({ streamingContent: content });
	},

	appendStreamingContent: (chunk) => {
		set((state) => ({
			streamingContent: state.streamingContent + chunk,
		}));
	},

	setMemoryContext: (context, messageId) => {
		set({
			memoryContext: context,
			lastMessageMemoryContext: messageId ?? null,
		});
	},

	clearMessages: () => {
		set({
			messages: [],
			streamingContent: "",
			memoryContext: null,
			lastMessageMemoryContext: null,
		});
	},
}));
