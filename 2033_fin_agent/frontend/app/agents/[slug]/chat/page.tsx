"use client";

import { useState, useRef, useEffect } from "react";
import { apiClient } from "@/lib/api/client";
import { consumeSseStream } from "@/lib/chat/sse-parser";
import { useChatStore } from "@/stores/chat-store";
import type { ChatMessage, SessionDetail } from "@/lib/api/types";

interface ChatPageProps {
  params: { slug: string };
}

export default function ChatPage({ params }: ChatPageProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [agentName, setAgentName] = useState(params.slug);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    streamingText,
    isStreaming,
    error,
    addUserMessage,
    startAssistantMessage,
    appendToken,
    completeAssistantMessage,
    setError,
    loadMessages,
    clear,
  } = useChatStore();

  useEffect(() => {
    return () => {
      clear();
      setSessionId(null);
    };
  }, [params.slug, clear]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const session: SessionDetail = await apiClient.POST("/api/sessions", {
      agent_slug: params.slug,
    });
    setSessionId(session.id);
    setAgentName(session.agent_name);
    if (session.messages.length > 0) {
      loadMessages(session.messages);
    }
    return session.id;
  }

  async function loadExistingSession(sid: string) {
    const session: SessionDetail = await apiClient.GET(`/api/sessions/${sid}`);
    if (session.messages.length > 0) {
      loadMessages(session.messages);
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");

    let sid = sessionId;
    try {
      if (!sid) {
        sid = await ensureSession();
      }
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        finish_reason: null,
        created_at: new Date().toISOString(),
      };
      addUserMessage(userMsg);

      const res = await apiClient.POST_SSE(
        `/api/sessions/${sid}/messages`,
        { content: text }
      );

      if (!res.ok) {
        const errText = await res.text();
        let detail = errText;
        try {
          const parsed = JSON.parse(errText);
          detail = parsed.detail?.detail ?? parsed.detail ?? errText;
        } catch {
          // not JSON
        }
        setError(`API ${res.status}: ${detail}`);
        return;
      }

      await consumeSseStream(res, (event) => {
        switch (event.type) {
          case "message_start":
            startAssistantMessage(event.message_id);
            break;
          case "token":
            appendToken(event.delta);
            break;
          case "message_complete":
            completeAssistantMessage(event.message_id, event.finish_reason);
            break;
          case "error":
            setError(event.message);
            break;
          case "done":
            break;
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  return (
    <div className="flex flex-col h-full">
      <header className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">{agentName}</h2>
          <p className="text-xs text-zinc-500">slug: {params.slug}</p>
        </div>
        {sessionId && (
          <button
            onClick={() => loadExistingSession(sessionId)}
            className="text-xs text-zinc-500 hover:text-zinc-300 px-2 py-1 rounded border border-zinc-800"
          >
            Reload
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-800 text-zinc-100"
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.finish_reason === "error" && (
                <div className="text-xs text-red-400 mt-1">
                  Error generating response
                </div>
              )}
            </div>
          </div>
        ))}

        {isStreaming && streamingText && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-2 text-sm bg-zinc-800 text-zinc-100">
              <div className="whitespace-pre-wrap">{streamingText}</div>
              <span className="inline-block w-1.5 h-4 bg-zinc-400 animate-pulse ml-0.5 align-text-bottom" />
            </div>
          </div>
        )}

        {error && (
          <div className="text-center text-sm text-red-400 py-2">{error}</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-zinc-800 p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              isStreaming
                ? "Waiting for response..."
                : "Type a message..."
            }
            disabled={isStreaming}
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
