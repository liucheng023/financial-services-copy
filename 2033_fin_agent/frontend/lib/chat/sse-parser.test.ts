import { describe, it, expect } from "vitest";
import { parseSseEvent } from "@/lib/chat/sse-parser";

describe("parseSseEvent", () => {
  it("parses message_start", () => {
    const raw = 'event: message_start\ndata: {"message_id": "abc-123", "session_id": "ses-456"}';
    const evt = parseSseEvent(raw);
    expect(evt).toEqual({
      type: "message_start",
      message_id: "abc-123",
      session_id: "ses-456",
    });
  });

  it("parses token", () => {
    const raw = 'event: token\ndata: {"delta": "Hello"}';
    const evt = parseSseEvent(raw);
    expect(evt).toEqual({ type: "token", delta: "Hello" });
  });

  it("parses message_complete", () => {
    const raw = 'event: message_complete\ndata: {"message_id": "abc-123", "finish_reason": "stop"}';
    const evt = parseSseEvent(raw);
    expect(evt).toEqual({
      type: "message_complete",
      message_id: "abc-123",
      finish_reason: "stop",
    });
  });

  it("parses error", () => {
    const raw = 'event: error\ndata: {"code": "timeout", "message": "LLM timed out", "recoverable": false}';
    const evt = parseSseEvent(raw);
    expect(evt).toEqual({
      type: "error",
      code: "timeout",
      message: "LLM timed out",
      recoverable: false,
    });
  });

  it("parses done with empty data", () => {
    const raw = "event: done\ndata: {}";
    const evt = parseSseEvent(raw);
    expect(evt).toEqual({ type: "done" });
  });

  it("returns null for empty string", () => {
    expect(parseSseEvent("")).toBeNull();
  });

  it("returns null for unknown event name", () => {
    const raw = 'event: unknown\ndata: {}';
    expect(parseSseEvent(raw)).toBeNull();
  });
});
