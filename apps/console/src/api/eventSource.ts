/**
 * Fetch-based EventSource. The native constructor cannot set Last-Event-ID on a
 * fresh connection, and it cannot send an Authorization header. Comment lines
 * (the API's heartbeat) are ignored.
 */
type StreamInit = EventSourceInit & { headers?: Record<string, string> };

export class HeaderEventSource extends EventTarget {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  readonly url: string;
  withCredentials = false;
  readyState = HeaderEventSource.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  private readonly controller = new AbortController();
  private stopped = false;

  constructor(url: string, init?: StreamInit) {
    super();
    this.url = url;
    const requestHeaders = new Headers(init?.headers);
    if (!requestHeaders.has("Accept")) requestHeaders.set("Accept", "text/event-stream");
    void this.pump(url, requestHeaders);
  }

  close(): void {
    this.stopped = true;
    this.readyState = HeaderEventSource.CLOSED;
    this.controller.abort();
  }

  private async pump(url: string, requestHeaders: Headers): Promise<void> {
    try {
      const response = await fetch(url, { headers: requestHeaders, signal: this.controller.signal });
      if (this.stopped) return;
      if (!response.ok || !response.body) {
        this.fail();
        return;
      }
      this.readyState = HeaderEventSource.OPEN;
      const open = new Event("open");
      this.onopen?.(open);
      this.dispatchEvent(open);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!this.stopped) {
        const chunk = await reader.read();
        if (this.stopped) return;
        if (chunk.done) {
          this.finish();
          return;
        }
        buffer += decoder.decode(chunk.value, { stream: true });
        buffer = this.consume(buffer);
      }
    } catch {
      if (!this.stopped) this.fail();
    }
  }

  private consume(buffer: string): string {
    const parts = buffer.split(/\n\n/);
    const rest = parts.pop() ?? "";
    for (const part of parts) this.dispatchBlock(part);
    return rest;
  }

  private dispatchBlock(block: string): void {
    let name = "message";
    const data: string[] = [];
    let id = "";
    let sawData = false;
    for (const rawLine of block.split("\n")) {
      const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
      if (!line || line.startsWith(":")) continue;
      const splitAt = line.indexOf(":");
      const field = splitAt === -1 ? line : line.slice(0, splitAt);
      let value = splitAt === -1 ? "" : line.slice(splitAt + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") name = value;
      else if (field === "data") {
        data.push(value);
        sawData = true;
      } else if (field === "id") id = value;
    }
    if (!sawData) return;
    const message = new MessageEvent(name, { data: data.join("\n"), lastEventId: id });
    if (name === "message") this.onmessage?.(message);
    this.dispatchEvent(message);
  }

  private fail(): void {
    if (this.stopped) return;
    this.stopped = true;
    this.readyState = HeaderEventSource.CLOSED;
    const error = new Event("error");
    this.onerror?.(error);
    this.dispatchEvent(error);
  }

  private finish(): void {
    if (this.stopped) return;
    this.stopped = true;
    this.readyState = HeaderEventSource.CLOSED;
    this.dispatchEvent(new Event("end"));
  }
}

export function installEventSource(): void {
  if (typeof window === "undefined") return;
  window.EventSource = HeaderEventSource as unknown as typeof EventSource;
}
