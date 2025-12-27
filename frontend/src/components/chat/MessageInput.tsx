import { useState, useCallback } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useChatStore } from '@/features/chat/stores/chatStore';
import { useChat } from '@/features/chat/hooks/useChat';
import { cn } from '@/lib/utils';

export function MessageInput() {
  const [input, setInput] = useState('');
  const { sendMessage, isLoading } = useChat();
  const isStreaming = useChatStore((state) => state.isStreaming);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!input.trim() || isLoading || isStreaming) return;

      const message = input.trim();
      setInput('');
      await sendMessage(message);
    },
    [input, isLoading, isStreaming, sendMessage]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    },
    [handleSubmit]
  );

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type a message..."
        disabled={isLoading || isStreaming}
        className={cn(
          'flex-1 rounded-lg border bg-background px-4 py-2',
          'focus:outline-none focus:ring-2 focus:ring-primary',
          'disabled:cursor-not-allowed disabled:opacity-50'
        )}
      />
      <button
        type="submit"
        disabled={!input.trim() || isLoading || isStreaming}
        className={cn(
          'rounded-lg bg-primary px-4 py-2 text-primary-foreground',
          'hover:bg-primary/90',
          'disabled:cursor-not-allowed disabled:opacity-50'
        )}
      >
        {isLoading || isStreaming ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <Send className="h-5 w-5" />
        )}
      </button>
    </form>
  );
}
