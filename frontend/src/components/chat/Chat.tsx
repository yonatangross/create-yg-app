import { useRef, useEffect } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useChatStore } from '@/features/chat/stores/chatStore';

export function Chat() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const messages = useChatStore((state) => state.messages);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto max-w-3xl">
          <MessageList />
        </div>
      </div>
      <div className="border-t p-4">
        <div className="mx-auto max-w-3xl">
          <MessageInput />
        </div>
      </div>
    </div>
  );
}
