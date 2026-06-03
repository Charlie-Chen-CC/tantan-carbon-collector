/**
 * AI 聊天 hook - 修复 3.5 消息重复插入 bug
 *
 * 关键设计：
 *   - 用 useRef 跟踪当前对话 ID，避免 sendMessage 中途 convId 改变导致双重更新
 *   - 用 immutable update，确保 React 检测到变化
 *   - 持久化到 localStorage（key: 'ai_conversations'）
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { chatApi } from '../services/api';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  timestamp?: string;
}

export interface AIConversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
}

const STORAGE_KEY = 'ai_conversations';

const genId = (): string => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const loadFromStorage = (): AIConversation[] => {
  if (typeof window === 'undefined') return [];
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
};

export interface UseAIChatReturn {
  conversations: AIConversation[];
  currentConvId: string | null;
  currentMessages: ChatMessage[];
  isLoading: boolean;
  inputMessage: string;
  setInputMessage: (v: string) => void;
  setCurrentConvId: (id: string | null) => void;
  sendMessage: (sessionId: string, currentSection: number) => Promise<void>;
  newConversation: () => void;
}

export const useAIChat = (): UseAIChatReturn => {
  const [conversations, setConversations] = useState<AIConversation[]>(loadFromStorage);
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  // 防止在 sendMessage 异步过程中 currentConvId 改变导致双重追加
  const activeConvIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  const newConversation = useCallback(() => {
    const conv: AIConversation = {
      id: genId(),
      title: '新对话',
      messages: [],
      createdAt: new Date().toISOString(),
    };
    setConversations((prev) => [conv, ...prev]);
    setCurrentConvId(conv.id);
    activeConvIdRef.current = conv.id;
    setInputMessage('');
  }, []);

  const sendMessage = useCallback(
    async (sessionId: string, currentSection: number) => {
      const text = inputMessage.trim();
      if (!text || !sessionId) return;

      // 锁定一个 convId（本次发送期间不变）
      let convId = activeConvIdRef.current ?? currentConvId;
      if (!convId) {
        const conv: AIConversation = {
          id: genId(),
          title: text.slice(0, 20),
          messages: [],
          createdAt: new Date().toISOString(),
        };
        setConversations((prev) => [conv, ...prev]);
        setCurrentConvId(conv.id);
        convId = conv.id;
      }
      activeConvIdRef.current = convId;

      const userMsg: ChatMessage = {
        role: 'user',
        content: text,
        timestamp: new Date().toISOString(),
      };
      // immutable update：基于函数式 setState，避免基于旧 conversations 读再写
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? { ...c, messages: [...c.messages, userMsg], title: text.slice(0, 20) || c.title }
            : c,
        ),
      );
      setInputMessage('');
      setIsLoading(true);

      try {
        const response = await chatApi.send(sessionId, text, { current_section: currentSection });
        const assistantMsg: ChatMessage = {
          role: 'assistant',
          content: response.data.content,
          intent: response.data.intent,
          timestamp: new Date().toISOString(),
        };
        // 关键：仍用 ref 而非 state，防止异步过程中 currentConvId 已变导致写到错误对话
        const finalConvId = activeConvIdRef.current ?? convId;
        setConversations((prev) =>
          prev.map((c) =>
            c.id === finalConvId ? { ...c, messages: [...c.messages, assistantMsg] } : c,
          ),
        );
      } catch {
        // 简单降级：把错误作为 assistant message 追加
        const errMsg: ChatMessage = {
          role: 'assistant',
          content: '抱歉，发送消息失败。',
          timestamp: new Date().toISOString(),
        };
        setConversations((prev) =>
          prev.map((c) => (c.id === convId ? { ...c, messages: [...c.messages, errMsg] } : c)),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [inputMessage, currentConvId],
  );

  const currentConversation = conversations.find((c) => c.id === currentConvId);
  const currentMessages = currentConversation?.messages ?? [];

  return {
    conversations,
    currentConvId,
    currentMessages,
    isLoading,
    inputMessage,
    setInputMessage,
    setCurrentConvId,
    sendMessage,
    newConversation,
  };
};
