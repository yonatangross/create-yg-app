import { useState } from "react";
import { Brain, ChevronDown, ChevronUp } from "lucide-react";
import type { MemoryItem } from "@/types";

interface MemoryContextPanelProps {
	memories: MemoryItem[];
	isExpanded?: boolean;
}

export function MemoryContextPanel({
	memories,
	isExpanded: initialExpanded = false,
}: MemoryContextPanelProps) {
	const [isExpanded, setIsExpanded] = useState(initialExpanded);

	if (memories.length === 0) {
		return null;
	}

	return (
		<div className="rounded-lg border border-muted bg-muted/50 overflow-hidden">
			<button
				type="button"
				onClick={() => setIsExpanded(!isExpanded)}
				className="flex w-full items-center justify-between gap-2 px-4 py-3 text-sm font-medium hover:bg-muted/70 transition-colors"
			>
				<div className="flex items-center gap-2">
					<Brain className="h-4 w-4 text-primary" />
					<span>Memory Context</span>
					<span className="inline-flex items-center justify-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
						{memories.length}
					</span>
				</div>
				{isExpanded ? (
					<ChevronUp className="h-4 w-4 text-muted-foreground" />
				) : (
					<ChevronDown className="h-4 w-4 text-muted-foreground" />
				)}
			</button>

			{isExpanded && (
				<div className="border-t border-muted bg-background/50 px-4 py-3">
					<div className="space-y-3">
						{memories.map((memory, index) => (
							<div
								key={`${memory.type}-${index}`}
								className="rounded-md bg-muted/30 p-3 text-sm"
							>
								<div className="mb-1 flex items-center gap-2">
									<span className="inline-flex items-center rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
										{memory.type}
									</span>
								</div>
								<p className="text-muted-foreground leading-relaxed">
									{memory.content}
								</p>
							</div>
						))}
					</div>
				</div>
			)}
		</div>
	);
}
