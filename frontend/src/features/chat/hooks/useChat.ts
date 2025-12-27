import { useState, useCallback } from 'react';
import { useChatStore } from '../stores/chatStore';

export function useChat() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    addMessage,
    updateMessage,
    setStreaming,
    setStreamingContent,
    appendStreamingContent,
  } = useChatStore();

  const sendMessage = useCallback(
    async (content: string) => {
      setIsLoading(true);
      setError(null);

      // Add user message
      addMessage({ role: 'user', content });

      // Add placeholder for assistant message
      const assistantId = addMessage({ role: 'assistant', content: '' });

      try {
        setStreaming(true);
        setStreamingContent('');

        const response = await fetch('/api/v1/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('No response body');
        }

        let fullContent = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;

              try {
                const parsed = JSON.parse(data);
                if (parsed.chunk) {
                  fullContent += parsed.chunk;
                  appendStreamingContent(parsed.chunk);
                  updateMessage(assistantId, fullContent);
                }
              } catch {
                // Not JSON, might be plain text token
                fullContent += data;
                appendStreamingContent(data);
                updateMessage(assistantId, fullContent);
              }
            } else if (line.startsWith('event: token')) {
              // Handle SSE token event
            } else if (line.startsWith('event: complete')) {
              // Stream complete
            }
          }
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
        updateMessage(assistantId, `Error: ${message}`);
      } finally {
        setStreaming(false);
        setIsLoading(false);
      }
    },
    [addMessage, updateMessage, setStreaming, setStreamingContent, appendStreamingContent]
  );

  return {
    sendMessage,
    isLoading,
    error,
  };
}
