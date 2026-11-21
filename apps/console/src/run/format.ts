import { copy } from "../copy";

export function formatCount(value: number): string {
  const whole = Math.trunc(value);
  const sign = whole < 0 ? "-" : "";
  const digits = String(Math.abs(whole));
  return sign + digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ${copy.unitMs}`;
  const seconds = ms / 1000;
  const text = seconds < 10 ? seconds.toFixed(1) : String(Math.round(seconds));
  return `${text} ${copy.unitSeconds}`;
}

export function formatElapsed(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return `0 ${copy.unitMs}`;
  if (ms < 1000) return `${Math.round(ms)} ${copy.unitMs}`;
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds} ${copy.unitSeconds}`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}${copy.unitMinutes} ${String(seconds).padStart(2, "0")}${copy.unitSeconds}`;
}

export function formatCost(value: number | null | undefined): string {
  if (value == null) return copy.costUnknown;
  if (value === 0) return "$0.00";
  const abs = Math.abs(value);
  const digits = abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return `$${value.toFixed(digits)}`;
}

export function formatStamp(ts: string | null | undefined): string {
  if (!ts) return copy.emdash;
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/.exec(ts);
  if (!match) return copy.emdash;
  return `${match[1]} ${match[2]} ${copy.utc}`;
}

export function formatClock(ts: string | null | undefined): string {
  if (!ts) return copy.emdash;
  const match = /T(\d{2}:\d{2}:\d{2})/.exec(ts);
  if (!match) return copy.emdash;
  return `${match[1]} ${copy.utc}`;
}

export function statusTone(status: string | null | undefined): "ok" | "warn" | "bad" | "live" | "neutral" {
  if (!status) return "neutral";
  if (status === "running") return "live";
  if (status === "failed" || status === "refused" || status === "design_invalid") return "bad";
  if (status === "paused" || status === "escalated" || status.startsWith("awaiting")) return "warn";
  if (status === "built" || status === "answered" || status === "up_to_date" || status === "finished") return "ok";
  return "neutral";
}
