/** Same-origin `/v1` unless VITE_API_BASE points somewhere else. `/` means the dev proxy. */
export function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE ?? "";
  if (raw === "" || raw === "/") return "";
  return raw.replace(/\/$/, "");
}

export function apiUrl(path: string): string {
  return `${apiBase()}${path}`;
}
