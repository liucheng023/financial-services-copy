import type { SseEvent } from "@/lib/api/types";

export function parseSseEvent(raw: string): SseEvent | null {
  let eventName = "";
  let dataRaw = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataRaw = line.slice("data:".length).trim();
    }
  }
  if (!eventName) return null;
  const data = dataRaw ? JSON.parse(dataRaw) : {};
  switch (eventName) {
    case "message_start":
      return {
        type: "message_start",
        message_id: data.message_id,
        session_id: data.session_id,
      };
    case "token":
      return { type: "token", delta: data.delta };
    case "message_complete":
      return {
        type: "message_complete",
        message_id: data.message_id,
        finish_reason: data.finish_reason,
      };
    case "error":
      return {
        type: "error",
        code: data.code,
        message: data.message,
        recoverable: data.recoverable,
      };
    case "done":
      return { type: "done" };
    default:
      return null;
  }
}

export async function consumeSseStream(
  response: Response,
  onEvent: (event: SseEvent) => void
): Promise<void> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const raw of parts) {
      const trimmed = raw.trim();
      if (!trimmed) continue;
      const evt = parseSseEvent(trimmed);
      if (evt) onEvent(evt);
    }
  }
  if (buffer.trim()) {
    const evt = parseSseEvent(buffer.trim());
    if (evt) onEvent(evt);
  }
}
