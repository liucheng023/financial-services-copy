import { create } from "zustand";
import type { ChatMessage } from "@/lib/api/types";

interface ChatState {
  messages: ChatMessage[];
  streamingMessageId: string | null;
  streamingText: string;
  isStreaming: boolean;
  error: string | null;

  addUserMessage: (msg: ChatMessage) => void;
  startAssistantMessage: (messageId: string) => void;
  appendToken: (delta: string) => void;
  completeAssistantMessage: (messageId: string, finishReason: string) => void;
  setError: (error: string) => void;
  resetStream: () => void;
  loadMessages: (messages: ChatMessage[]) => void;
  clear: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  streamingMessageId: null,
  streamingText: "",
  isStreaming: false,
  error: null,

  addUserMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  startAssistantMessage: (messageId) =>
    set({ streamingMessageId: messageId, streamingText: "", isStreaming: true, error: null }),

  appendToken: (delta) =>
    set((s) => ({ streamingText: s.streamingText + delta })),

  completeAssistantMessage: (messageId, finishReason) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: messageId,
          role: "assistant" as const,
          content: s.streamingText,
          finish_reason: finishReason,
          created_at: new Date().toISOString(),
        },
      ],
      streamingMessageId: null,
      streamingText: "",
      isStreaming: false,
    })),

  setError: (error) =>
    set((s) => ({
      error,
      isStreaming: false,
      messages: s.streamingMessageId
        ? [
            ...s.messages,
            {
              id: s.streamingMessageId,
              role: "assistant" as const,
              content: s.streamingText || "",
              finish_reason: "error",
              created_at: new Date().toISOString(),
            },
          ]
        : s.messages,
      streamingMessageId: null,
      streamingText: "",
    })),

  resetStream: () =>
    set({ streamingMessageId: null, streamingText: "", isStreaming: false, error: null }),

  loadMessages: (messages) =>
    set({ messages, streamingMessageId: null, streamingText: "", isStreaming: false, error: null }),

  clear: () =>
    set({ messages: [], streamingMessageId: null, streamingText: "", isStreaming: false, error: null }),
}));
