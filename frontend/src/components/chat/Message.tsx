import { cn } from "@/lib/utils";
import type { Message as MessageType } from "@/features/chat/stores/chatStore";
import type { MemoryContext } from "@/types";
import ReactMarkdown from "react-markdown";
import { User, Bot } from "lucide-react";
import { MemoryContextPanel } from "./MemoryContextPanel";

interface MessageProps {
	message: MessageType;
	memoryContext?: MemoryContext | null;
}

export function Message({ message, memoryContext }: MessageProps) {
	const isUser = message.role === "user";

	return (
		<div className="space-y-2">
			{/* Show memory context panel above assistant messages */}
			{!isUser && memoryContext && memoryContext.memories.length > 0 && (
				<MemoryContextPanel memories={memoryContext.memories} />
			)}

			<div
				className={cn(
					"flex gap-3 rounded-lg p-4",
					isUser ? "bg-muted" : "bg-background",
				)}
			>
				<div
					className={cn(
						"flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
						isUser ? "bg-primary text-primary-foreground" : "bg-muted",
					)}
				>
					{isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
				</div>
				<div className="flex-1 overflow-hidden">
					<div className="prose prose-sm max-w-none dark:prose-invert">
						<ReactMarkdown>{message.content}</ReactMarkdown>
					</div>
				</div>
			</div>
		</div>
	);
}
