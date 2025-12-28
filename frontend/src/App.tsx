import { Chat } from "@/components/chat/Chat";
import { Header } from "@/components/layout/Header";

function App() {
	return (
		<div className="flex h-screen flex-col bg-background">
			<Header />
			<main className="flex-1 overflow-hidden">
				<Chat />
			</main>
		</div>
	);
}

export default App;
