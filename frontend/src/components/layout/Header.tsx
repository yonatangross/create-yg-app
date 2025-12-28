import { MessageSquare } from "lucide-react";

export function Header() {
	return (
		<header className="flex h-14 items-center border-b px-6">
			<div className="flex items-center gap-2">
				<MessageSquare className="h-6 w-6 text-primary" />
				<h1 className="text-lg font-semibold">YG Starter</h1>
			</div>
		</header>
	);
}
